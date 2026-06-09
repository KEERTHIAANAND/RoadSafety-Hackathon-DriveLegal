from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import ChatRequest, ChatResponse, ChallanRequest, ChallanResponse
from app.agent.orchestrator import agent_executor
from app.db.challan_db import challan_db
from app.agent.tools import resolve_location
import fitz # PyMuPDF
import httpx
from groq import Groq
import json

app = FastAPI(title="DriveLegal Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    if not agent_executor:
        raise HTTPException(status_code=500, detail="Agent is not configured (missing API key?)")

    # Resolve location context if coordinates provided
    location_context = ""
    if request.latitude and request.longitude:
        try:
            loc_result = resolve_location.invoke({'latitude': request.latitude, 'longitude': request.longitude})
            location_context = f"\n\nSystem Note: The user's current location is {loc_result}. Use this if relevant."
        except Exception as e:
            print(f"Failed to resolve location: {e}")

    # Format chat history
    messages = []
    if request.chat_history:
        for msg in request.chat_history:
            messages.append({"role": msg.role, "content": msg.content})

    # Combine query with location context
    full_input = request.query + location_context
    messages.append({"role": "user", "content": full_input})

    try:
        result = agent_executor.invoke({"messages": messages})
        
        # Result contains all messages. We want the last AIMessage content.
        if "messages" in result and len(result["messages"]) > 0:
            output_text = result["messages"][-1].content
        else:
            output_text = "I'm sorry, I couldn't generate a response."
            
        return ChatResponse(response=output_text)
    except Exception as e:
        error_msg = str(e)
        if "tool_use_failed" in error_msg:
            return ChatResponse(response="I'm sorry, my tool execution failed due to a formatting error. Could you please rephrase your question?")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/calculate-challan", response_model=ChallanResponse)
def calculate_challan_endpoint(request: ChallanRequest):
    fine_details = challan_db.get_fine(
        violation=request.violation,
        vehicle_type=request.vehicle_type,
        state=request.state
    )
    return ChallanResponse(fine_details=fine_details)

@app.get("/violations")
def list_violations():
    # Return available violation codes from the DB
    if challan_db.df.empty:
        return {"violations": []}
    
    violations = challan_db.df[['violation_code', 'violation_description']].to_dict('records')
    return {"violations": violations}

@app.post("/scan-challan")
async def scan_challan_endpoint(file: UploadFile = File(...)):
    filename = file.filename
    content_type = file.content_type
    file_bytes = await file.read()
    
    extracted_text = ""
    
    # 1. Extract text based on file type
    if filename.lower().endswith(".pdf"):
        # PDF parsing
        try:
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            text_list = []
            for page in pdf_doc:
                text_list.append(page.get_text())
            extracted_text = "\n".join(text_list)
            pdf_doc.close()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
        # Image parsing using OCR.Space API fallback
        try:
            async with httpx.AsyncClient() as client:
                # Prepare payload
                payload = {
                    'apikey': 'helloworld',
                    'language': 'eng',
                }
                files = {'file': (filename, file_bytes, content_type)}
                response = await client.post('https://api.ocr.space/parse/image', data=payload, files=files, timeout=20.0)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ParsedResults"):
                        extracted_text = result['ParsedResults'][0]['ParsedText']
                    else:
                        raise Exception("OCR failed or returned empty results")
                else:
                    raise Exception(f"OCR API returned status {response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Image OCR failed: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, PNG, or JPG.")
        
    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text from the document.")
        
    # 2. Use Groq to parse the text into structured json
    from app.config import GROQ_API_KEY
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set.")
        
    client = Groq(api_key=GROQ_API_KEY)
    
    prompt = f"""
Analyze the following extracted text from a traffic violation ticket / challan.
Extract the key violation parameters and return ONLY a valid JSON object. Do not include any markdown formatting, thoughts, or extra text.

JSON Schema:
{{
  "violation_keyword": "1-3 word keyword describing the main violation (e.g. speeding, drunk driving, helmet, overage vehicle, no license)",
  "vehicle_type": "2-wheeler, 4-wheeler, transport, or LMV",
  "state": "State name (e.g. Delhi, Tamil Nadu, Karnataka)",
  "ticket_fine": "Fine amount mentioned on the ticket (as a number or 'Not specified')",
  "section": "Legal section cited (e.g. Section 183, Section 184, Section 182B)",
  "summary": "Brief summary of the violation details"
}}

Extracted Challan Text:
{extracted_text}
"""
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0,
            response_format={"type": "json_object"}
        )
        parsed_data = json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to structure extracted text: {str(e)}")
        
    # 3. Query local database to double check and advise
    violation = parsed_data.get("violation_keyword", "general")
    vehicle = parsed_data.get("vehicle_type", "all")
    state = parsed_data.get("state", "national")
    
    db_fine_info = challan_db.get_fine(violation, vehicle, state)
    
    # 4. Synthesize advice
    advice_prompt = f"""
You are a legal advisor for traffic rules.
The user has scanned a challan:
- Violation: {violation}
- State: {state}
- Section Cited: {parsed_data.get("section")}
- Ticket Fine: {parsed_data.get("ticket_fine")}
- Summary: {parsed_data.get("summary")}

Database Reference Info:
{db_fine_info}

Formulate a response detailing:
1. **Verification**: Is the fine amount listed on the ticket correct according to Section/DB Rules?
2. **Payment & Resolution**: How and where the user should pay it (e.g. official Virtual Court / e-Challan portal).
3. **Contestation Grounds**: Are there any potential legal arguments to contest or appeal this challan? (e.g. wrong section code, wrong vehicle classification, wrong overage vehicle calculation).
Keep it structured, clear, and highly helpful.
"""
    try:
        advice_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": advice_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.2
        )
        advice_text = advice_completion.choices[0].message.content
    except Exception as e:
        advice_text = f"Analyzed challan details: {parsed_data.get('summary')}. Database lookup returned:\n{db_fine_info}"
        
    return {
        "success": True,
        "extracted_data": parsed_data,
        "database_info": db_fine_info,
        "legal_advice": advice_text
    }

