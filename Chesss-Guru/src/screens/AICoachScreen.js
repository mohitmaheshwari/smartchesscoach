import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, FlatList, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { COLORS } from '../constants/config';
import { sendCoachMessage } from '../services/api';

export default function AICoachScreen() {
  const [messages, setMessages] = useState([
    {
      id: '1',
      sender: 'coach',
      text: 'Greetings, Chess Champion! I am Grandmaster Guru, your AI chess mentor. Ask me anything about openings, tactical calculations, or game strategy!',
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!inputText.trim() || sending) return;

    const userMsg = {
      id: Date.now().toString(),
      sender: 'user',
      text: inputText.trim(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setSending(true);

    try {
      const history = messages.map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));

      const response = await sendCoachMessage(userMsg.text, history);

      const coachMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'coach',
        text: response.reply || 'Great question! Focus on piece activity and king safety.',
      };

      setMessages((prev) => [...prev, coachMsg]);
    } catch (e) {
      console.warn('Coach error:', e);
    } finally {
      setSending(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      {/* Top Persona Bar */}
      <View style={styles.personaBar}>
        <Text style={styles.avatar}>🧙‍♂️</Text>
        <View style={styles.personaInfo}>
          <Text style={styles.personaName}>Grandmaster Guru</Text>
          <Text style={styles.personaStatus}>● Online  •  Powered by Stockfish & Emergent LLM</Text>
        </View>
      </View>

      {/* Messages List */}
      <FlatList
        data={messages}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messagesContainer}
        renderItem={({ item }) => (
          <View
            style={[
              styles.messageBubble,
              item.sender === 'user' ? styles.userBubble : styles.coachBubble,
            ]}
          >
            <Text
              style={[
                styles.messageText,
                item.sender === 'user' ? styles.userMessageText : styles.coachMessageText,
              ]}
            >
              {item.text}
            </Text>
          </View>
        )}
      />

      {/* Input Row */}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.textInput}
          placeholder="Ask Guru about moves, openings, blunders..."
          placeholderTextColor={COLORS.textMuted}
          value={inputText}
          onChangeText={setInputText}
          onSubmitEditing={handleSend}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.sendButton, (!inputText.trim() || sending) && styles.sendButtonDisabled]}
          onPress={handleSend}
          disabled={!inputText.trim() || sending}
          activeOpacity={0.8}
        >
          {sending ? (
            <ActivityIndicator size="small" color="#000" />
          ) : (
            <Text style={styles.sendButtonText}>Send ➔</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  personaBar: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    backgroundColor: COLORS.cardBg,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.cardBorder,
  },
  avatar: {
    fontSize: 28,
    marginRight: 12,
  },
  personaInfo: {
    flex: 1,
  },
  personaName: {
    color: COLORS.primary,
    fontWeight: '800',
    fontSize: 16,
  },
  personaStatus: {
    color: COLORS.success,
    fontSize: 11,
    marginTop: 2,
  },
  messagesContainer: {
    padding: 16,
    paddingBottom: 20,
  },
  messageBubble: {
    maxWidth: '82%',
    borderRadius: 16,
    padding: 14,
    marginVertical: 6,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: COLORS.primary,
    borderBottomRightRadius: 2,
  },
  coachBubble: {
    alignSelf: 'flex-start',
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    borderBottomLeftRadius: 2,
  },
  messageText: {
    fontSize: 14,
    lineHeight: 20,
  },
  userMessageText: {
    color: '#000',
    fontWeight: '600',
  },
  coachMessageText: {
    color: COLORS.text,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: COLORS.cardBg,
    borderTopWidth: 1,
    borderTopColor: COLORS.cardBorder,
  },
  textInput: {
    flex: 1,
    backgroundColor: '#0f172a',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: COLORS.text,
    fontSize: 14,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginRight: 8,
  },
  sendButton: {
    backgroundColor: COLORS.primary,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
  sendButtonText: {
    color: '#000',
    fontWeight: '800',
    fontSize: 13,
  },
});
