import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
  Alert,
  useWindowDimensions,
  Image,
  ScrollView,
} from 'react-native';
import {
  Send,
  MapPin,
  Scale,
  Plus,
  Mic,
  MessageSquare,
  Sparkles,
  Menu,
  FileText,
  Wifi,
  WifiOff,
} from 'lucide-react-native';
import * as Location from 'expo-location';
import * as DocumentPicker from 'expo-document-picker';
import { OFFLINE_CHALLAN_DB } from './offline_db';

// Message interfaces
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

const BACKEND_URL = Platform.select({
  android: 'http://10.0.2.2:8000',
  ios: 'http://localhost:8000',
  default: 'http://localhost:8000',
});

export default function ChatScreen() {
  const { width } = useWindowDimensions();
  const isLargeScreen = width > 768;

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isOffline, setIsOffline] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [location, setLocation] = useState<Location.LocationObject | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [recentChats, setRecentChats] = useState<string[]>([]);
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    fetchLocation();
  }, []);

  const fetchLocation = async () => {
    setIsLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Location Access',
          'Permission to access location was denied. Using national database.'
        );
        setIsLocating(false);
        return;
      }
      const currentLoc = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setLocation(currentLoc);
    } catch (error) {
      console.log('Error fetching location:', error);
    } finally {
      setIsLocating(false);
    }
  };

  const searchOfflineDB = (query: string): string => {
    const queryLower = query.toLowerCase();
    
    // 1. Exact match on violation code
    let matches = OFFLINE_CHALLAN_DB.filter(
      item => item.violation_code.toLowerCase() === queryLower
    );
    
    // 2. Fuzzy match on description
    if (matches.length === 0) {
      matches = OFFLINE_CHALLAN_DB.filter(
        item => item.violation_description.toLowerCase().includes(queryLower)
      );
    }
    
    // 3. Fallback: match words
    if (matches.length === 0) {
      const stopWords = ["the", "a", "an", "is", "for", "not", "wearing", "what", "fine", "my", "without", "what is the fine for"];
      const words = queryLower.split(/\s+/).filter(w => w.length > 2 && !stopWords.includes(w));
      if (words.length > 0) {
        matches = OFFLINE_CHALLAN_DB.filter(item => {
          const desc = item.violation_description.toLowerCase();
          return words.some(w => desc.includes(w));
        });
      }
    }
    
    if (matches.length === 0) {
      return "Offline Mode: No matching violation found in local database. Try words like 'helmet', 'speeding', 'license', or 'drunk'.";
    }
    
    return "Offline Mode Result:\n\n" + matches.map(item => {
      return `• Violation: ${item.violation_description}\n  Section: ${item.applicable_section} of ${item.act_name}\n  First Offence Fine: Rs. ${item.first_offence_fine || 'None'}\n  Repeat Offence Fine: Rs. ${item.repeat_offence_fine || 'None'}\n  Imprisonment: ${item.imprisonment_first || 'None'}\n  License Suspension: ${item.license_suspension || 'None'}\n  Notes: ${item.notes || 'None'}`;
    }).join('\n\n---\n\n');
  };

  const pickAndScanDocument = async () => {
    setIsUploading(true);
    try {
      let fileInfo: { uri: string, name: string, type: string, file?: any };
      
      if (Platform.OS === 'web') {
        fileInfo = await new Promise((resolve, reject) => {
          const input = document.createElement('input');
          input.type = 'file';
          input.accept = 'image/*,application/pdf';
          input.onchange = (e: any) => {
            const file = e.target.files[0];
            if (file) {
              resolve({
                uri: URL.createObjectURL(file),
                name: file.name,
                type: file.type,
                file: file
              });
            } else {
              reject(new Error('No file selected'));
            }
          };
          input.click();
        });
      } else {
        const result = await DocumentPicker.getDocumentAsync({
          type: ['image/*', 'application/pdf'],
          copyToCacheDirectory: true
        });
        
        if (result.assets && result.assets.length > 0) {
          const asset = result.assets[0];
          fileInfo = {
            uri: asset.uri,
            name: asset.name,
            type: asset.mimeType || 'application/octet-stream'
          };
        } else {
          throw new Error('No file selected');
        }
      }

      // Add user message for document upload
      const userMessage: Message = {
        id: Math.random().toString(),
        role: 'user',
        content: `Uploaded challan document for scanning: ${fileInfo.name}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      const formData = new FormData();
      if (Platform.OS === 'web' && fileInfo.file) {
        formData.append('file', fileInfo.file, fileInfo.name);
      } else {
        // Native upload payload
        formData.append('file', {
          uri: fileInfo.uri,
          name: fileInfo.name,
          type: fileInfo.type
        } as any);
      }

      const response = await fetch(`${BACKEND_URL}/scan-challan`, {
        method: 'POST',
        body: formData,
        headers: {
          'Accept': 'application/json',
        }
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to scan document');
      }

      const data = await response.json();
      
      const aiMessage: Message = {
        id: Math.random().toString(),
        role: 'assistant',
        content: `🔍 **Challan Scan Results**\n\n**Detected State:** ${data.extracted_data.state}\n**Section Cited:** ${data.extracted_data.section}\n**Offence:** ${data.extracted_data.violation_keyword}\n**Ticket Fine Amount:** ${data.extracted_data.ticket_fine}\n\n📝 **Legal Analysis & Advice:**\n${data.legal_advice}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);

    } catch (error: any) {
      console.error(error);
      const errMessage: Message = {
        id: Math.random().toString(),
        role: 'assistant',
        content: `❌ Scan Failed: ${error.message || 'Error processing the ticket scanner.'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMessage]);
    } finally {
      setIsUploading(false);
      setIsLoading(false);
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  const handleSend = async (textToSend?: string) => {
    const queryText = textToSend || inputText.trim();
    if (!queryText) return;

    setInputText('');

    // Save to recents if not already present
    if (!recentChats.includes(queryText)) {
      setRecentChats((prev) => [queryText, ...prev.slice(0, 7)]);
    }

    const userMessage: Message = {
      id: Math.random().toString(),
      role: 'user',
      content: queryText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    if (isOffline) {
      // Simulate brief network lag for offline lookup
      setTimeout(() => {
        const localResult = searchOfflineDB(queryText);
        const aiMessage: Message = {
          id: Math.random().toString(),
          role: 'assistant',
          content: localResult,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMessage]);
        setIsLoading(false);
        setTimeout(() => {
          flatListRef.current?.scrollToEnd({ animated: true });
        }, 100);
      }, 300);
      return;
    }

    const chatHistory: ChatHistoryItem[] = messages.map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));

    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: queryText,
          chat_history: chatHistory,
          latitude: location?.coords.latitude || null,
          longitude: location?.coords.longitude || null,
        }),
      });

      if (!response.ok) throw new Error('Network error');

      const data = await response.json();

      const aiMessage: Message = {
        id: Math.random().toString(),
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error(error);
      const errMessage: Message = {
        id: Math.random().toString(),
        role: 'assistant',
        content: 'Error connecting to the legal engine. Please check if your backend is running or switch to Offline Mode in the navigation bar.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMessage]);
    } finally {
      setIsLoading(false);
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  const renderMessageBubble = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[styles.chatRow, isUser ? styles.userRow : styles.assistantRow]}>
        {!isUser && (
          <View style={styles.assistantLogo}>
            <View style={styles.logoGradientWrapper}>
              <Sparkles size={14} color="#6366F1" />
            </View>
          </View>
        )}
        <View style={styles.textWrapper}>
          <Text style={[styles.bubbleText, isUser ? styles.userText : styles.assistantText]}>
            {item.content}
          </Text>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0e0e11" />
      <View style={{ flex: 1, flexDirection: 'row' }}>
        
        {/* Customized Sidebar */}
        {isLargeScreen && (
          <View style={[styles.sidebar, { width: sidebarExpanded ? 260 : 76, paddingHorizontal: sidebarExpanded ? 16 : 8, alignItems: sidebarExpanded ? 'stretch' : 'center' }]}>
            <View style={styles.sidebarTop}>
              {/* Toggle Menu button inside sidebar */}
              <TouchableOpacity 
                style={[styles.menuIconBtn, { marginBottom: 20, alignSelf: sidebarExpanded ? 'flex-start' : 'center', marginLeft: sidebarExpanded ? 4 : 0 }]} 
                onPress={() => setSidebarExpanded(!sidebarExpanded)}
              >
                <Menu size={20} color="#E3E3E3" />
              </TouchableOpacity>

              {/* Brand Logo & Title */}
              {sidebarExpanded ? (
                <View style={styles.brandContainer}>
                  <View style={styles.logoCircle}>
                    <Scale size={18} color="#6366F1" />
                  </View>
                  <Text style={styles.brandText}>DriveLegal</Text>
                </View>
              ) : (
                <View style={[styles.logoCircle, { marginBottom: 24, alignSelf: 'center' }]}>
                  <Scale size={18} color="#6366F1" />
                </View>
              )}

              {/* New Chat Button */}
              {sidebarExpanded ? (
                <TouchableOpacity style={styles.newChatButton} onPress={() => setMessages([])}>
                  <Plus size={18} color="#E3E3E3" style={{ marginRight: 10 }} />
                  <Text style={styles.newChatText}>New Chat</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity style={[styles.logoCircle, { backgroundColor: '#1e1f20', marginBottom: 24 }]} onPress={() => setMessages([])}>
                  <Plus size={18} color="#E3E3E3" />
                </TouchableOpacity>
              )}

              {/* Recent Chats Section */}
              {sidebarExpanded && recentChats.length > 0 && (
                <View style={styles.recentSection}>
                  <Text style={styles.recentHeading}>Recent Chats</Text>
                  <ScrollView style={styles.recentScroll}>
                    {recentChats.map((chat, idx) => (
                      <TouchableOpacity
                        key={idx}
                        style={styles.recentItem}
                        onPress={() => handleSend(chat)}
                      >
                        <MessageSquare size={14} color="#9E9E9E" style={{ marginRight: 8 }} />
                        <Text numberOfLines={1} style={styles.recentItemText}>
                          {chat}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </View>
              )}
            </View>

            {/* Bottom Only Profile Avatar View */}
            <View style={[styles.sidebarBottom, { width: '100%', alignItems: 'center', justifyContent: 'center' }]}>
              <View style={styles.avatarContainer}>
                <Image
                  source={{ uri: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&q=80' }}
                  style={styles.avatarImage}
                />
              </View>
            </View>
          </View>
        )}

        {/* Main Content Area */}
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.chatArea}
        >
          {/* Header Bar */}
          <View style={styles.navbar}>
            <View style={styles.navLeft}>
              {/* Only show Hamburger Menu button in navbar on Mobile (when sidebar is hidden) */}
              {!isLargeScreen && (
                <TouchableOpacity style={styles.menuIconBtn} onPress={() => setSidebarExpanded(!sidebarExpanded)}>
                  <Menu size={20} color="#E3E3E3" />
                </TouchableOpacity>
              )}
              {!isLargeScreen && (
                <Text style={styles.navTitle}>DriveLegal</Text>
              )}
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              {/* Geolocation Pill */}
              <TouchableOpacity onPress={fetchLocation} style={styles.geoPill}>
                {isLocating ? (
                  <ActivityIndicator size="small" color="#6366F1" style={{ marginRight: 6 }} />
                ) : (
                  <MapPin size={11} color={location ? '#10B981' : '#C4C7C5'} style={{ marginRight: 4 }} />
                )}
                <Text style={[styles.geoText, location ? styles.geoActive : styles.geoInactive]}>
                  {location ? 'Location Resolved' : 'Geolocated'}
                </Text>
              </TouchableOpacity>

              {/* Offline/Online Mode Pill */}
              <TouchableOpacity onPress={() => setIsOffline(!isOffline)} style={[styles.geoPill, { marginLeft: 8 }]}>
                {isOffline ? (
                  <WifiOff size={11} color="#EF4444" style={{ marginRight: 4 }} />
                ) : (
                  <Wifi size={11} color="#10B981" style={{ marginRight: 4 }} />
                )}
                <Text style={[styles.geoText, { color: isOffline ? '#EF4444' : '#10B981' }]}>
                  {isOffline ? 'Offline' : 'Online'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Main Body */}
          {messages.length === 0 ? (
            <View style={styles.centerHeroContainer}>
              <View style={styles.radialGlow} />
              
              {/* Traffic/Driving Centered Hero Text */}
              <Text style={styles.heroHeading}>Where are we driving today?</Text>

              {/* Central Pill Input */}
              <View style={styles.centerInputContainer}>
                <View style={styles.inputPill}>
                  <TouchableOpacity style={styles.actionBtn} onPress={pickAndScanDocument} title="Upload Ticket">
                    <FileText size={20} color="#6366F1" />
                  </TouchableOpacity>
                  
                  <TextInput
                    style={styles.textInput}
                    placeholder={isOffline ? "Search offline fines (e.g. helmet, speeding)..." : "Ask about traffic rules, fines, or road laws..."}
                    placeholderTextColor="#9E9E9E"
                    value={inputText}
                    onChangeText={setInputText}
                    onSubmitEditing={() => handleSend()}
                    multiline={false}
                  />

                  <View style={styles.modelChip}>
                    <Text style={styles.modelChipText}>{isOffline ? 'Local DB' : 'Llama-3.1-8B'} ▾</Text>
                  </View>

                  <TouchableOpacity style={styles.actionBtn}>
                    <Mic size={18} color="#C4C7C5" />
                  </TouchableOpacity>

                  {inputText.trim().length > 0 && (
                    <TouchableOpacity style={styles.actionBtn} onPress={() => handleSend()}>
                      <Send size={16} color="#6366F1" />
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            </View>
          ) : (
            // Active Chat Screen
            <View style={{ flex: 1 }}>
              <FlatList
                ref={flatListRef}
                data={messages}
                keyExtractor={(item) => item.id}
                renderItem={renderMessageBubble}
                contentContainerStyle={styles.chatListContent}
                onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
              />

              {/* Loader */}
              {isUploading ? (
                <View style={styles.loadingBox}>
                  <ActivityIndicator size="small" color="#6366F1" />
                  <Text style={styles.loadingText}>Running OCR and analyzing ticket details...</Text>
                </View>
              ) : isLoading ? (
                <View style={styles.loadingBox}>
                  <ActivityIndicator size="small" color="#6366F1" />
                  <Text style={styles.loadingText}>Analyzing statutes...</Text>
                </View>
              ) : null}

              {/* Bottom Fixed Pill Input (Only visible when chat is active) */}
              <View style={styles.bottomInputContainer}>
                <View style={styles.inputPill}>
                  <TouchableOpacity style={styles.actionBtn} onPress={pickAndScanDocument} title="Upload Ticket">
                    <FileText size={20} color="#6366F1" />
                  </TouchableOpacity>
                  
                  <TextInput
                    style={styles.textInput}
                    placeholder={isOffline ? "Search offline fines (e.g. helmet, speeding)..." : "Ask about traffic rules, fines, or road laws..."}
                    placeholderTextColor="#9E9E9E"
                    value={inputText}
                    onChangeText={setInputText}
                    onSubmitEditing={() => handleSend()}
                    multiline={false}
                  />

                  <View style={styles.modelChip}>
                    <Text style={styles.modelChipText}>{isOffline ? 'Local DB' : 'Llama-3.1-8B'} ▾</Text>
                  </View>

                  <TouchableOpacity style={styles.actionBtn}>
                    <Mic size={18} color="#C4C7C5" />
                  </TouchableOpacity>

                  {inputText.trim().length > 0 && (
                    <TouchableOpacity style={styles.actionBtn} onPress={() => handleSend()}>
                      <Send size={16} color="#6366F1" />
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            </View>
          )}
        </KeyboardAvoidingView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0e0e11',
  },
  sidebar: {
    width: 260,
    backgroundColor: '#131314',
    justifyContent: 'space-between',
    paddingVertical: 20,
    paddingHorizontal: 16,
    borderRightWidth: 0.5,
    borderRightColor: '#1F1F1F',
  },
  sidebarTop: {
    flex: 1,
  },
  brandContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
    paddingHorizontal: 4,
  },
  logoCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1E1F20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  brandText: {
    color: '#E3E3E3',
    fontSize: 18,
    fontWeight: '600',
  },
  newChatButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e1f20',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 24,
    marginBottom: 24,
    borderWidth: 0.5,
    borderColor: '#2F2F2F',
  },
  newChatText: {
    color: '#E3E3E3',
    fontSize: 14,
    fontWeight: '500',
  },
  recentSection: {
    flex: 1,
  },
  recentHeading: {
    color: '#9E9E9E',
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    paddingHorizontal: 4,
  },
  recentScroll: {
    flex: 1,
  },
  recentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    marginBottom: 4,
  },
  recentItemText: {
    color: '#C4C7C5',
    fontSize: 13,
    flex: 1,
  },
  sidebarBottom: {
    alignItems: 'flex-start',
    paddingHorizontal: 4,
    paddingTop: 16,
    borderTopWidth: 0.5,
    borderTopColor: '#1F1F1F',
  },
  avatarContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    overflow: 'hidden',
    borderWidth: 1.5,
    borderColor: '#6366F1',
  },
  avatarImage: {
    width: '100%',
    height: '100%',
  },
  chatArea: {
    flex: 1,
    backgroundColor: '#0e0e11',
  },
  navbar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    backgroundColor: '#0e0e11',
  },
  navLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  menuIconBtn: {
    marginRight: 8,
  },
  navTitle: {
    color: '#E3E3E3',
    fontSize: 20,
    fontWeight: '500',
    fontFamily: Platform.OS === 'ios' ? 'System' : 'sans-serif-medium',
  },
  navModelText: {
    color: '#9E9E9E',
    fontSize: 14,
    marginLeft: 6,
  },
  geoPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#131314',
    paddingVertical: 5,
    paddingHorizontal: 12,
    borderRadius: 14,
    borderWidth: 0.5,
    borderColor: '#2D2D2D',
  },
  geoText: {
    fontSize: 10,
    fontWeight: '500',
  },
  geoActive: {
    color: '#10B981',
  },
  geoInactive: {
    color: '#9E9E9E',
  },
  centerHeroContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
    position: 'relative',
  },
  radialGlow: {
    position: 'absolute',
    width: 500,
    height: 400,
    borderRadius: 250,
    backgroundColor: 'rgba(26, 54, 115, 0.25)',
    filter: 'blur(120px)',
    bottom: -50,
    zIndex: -1,
  },
  heroHeading: {
    fontSize: 40,
    color: '#FFFFFF',
    fontWeight: '400',
    textAlign: 'center',
    marginBottom: 40,
    letterSpacing: -0.5,
    fontFamily: Platform.OS === 'ios' ? 'System' : 'sans-serif-light',
  },
  centerInputContainer: {
    width: '100%',
    maxWidth: 720,
    alignItems: 'center',
  },
  bottomInputContainer: {
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 10,
    alignItems: 'center',
    backgroundColor: '#0e0e11',
  },
  inputPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e1f20',
    borderRadius: 32,
    paddingHorizontal: 16,
    paddingVertical: 8,
    width: '100%',
    maxWidth: 720,
    height: 60,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 3,
  },
  textInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 16,
    paddingHorizontal: 12,
    height: '100%',
    ...Platform.select({
      web: {
        outlineStyle: 'none',
      },
      default: {},
    }),
  },
  modelChip: {
    backgroundColor: '#2F2F2F',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
  },
  modelChipText: {
    color: '#E3E3E3',
    fontSize: 11,
    fontWeight: '500',
  },
  actionBtn: {
    padding: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chatListContent: {
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  chatRow: {
    flexDirection: 'row',
    marginVertical: 16,
    width: '100%',
  },
  userRow: {
    justifyContent: 'flex-end',
  },
  assistantRow: {
    justifyContent: 'flex-start',
  },
  assistantLogo: {
    width: 32,
    height: 32,
    borderRadius: 16,
    marginRight: 16,
    overflow: 'hidden',
  },
  logoGradientWrapper: {
    flex: 1,
    backgroundColor: '#1e1f20',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 0.5,
    borderColor: '#2F2F2F',
    borderRadius: 16,
  },
  textWrapper: {
    maxWidth: '85%',
  },
  bubbleText: {
    fontSize: 16,
    lineHeight: 24,
  },
  userText: {
    color: '#FFFFFF',
    backgroundColor: '#1e1f20',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    borderTopRightRadius: 4,
    overflow: 'hidden',
  },
  assistantText: {
    color: '#E3E3E3',
    paddingVertical: 4,
  },
  loadingBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
  },
  loadingText: {
    color: '#9E9E9E',
    fontSize: 13,
    marginLeft: 8,
  },
});
