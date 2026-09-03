import React, { useState, useRef, useEffect } from 'react';
import { FiSend } from 'react-icons/fi';

const ChatInterface = ({ messages, onSendMessage }) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) {
      onSendMessage(input);
      setInput('');
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>✦ AI Yordamchi</h2>
        <p>Formulalar, tahlil va Excel savollari</p>
      </div>
      
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="empty-chat">
              <strong>Excel bilan gaplashing</strong>
              <p>Masalan: “A ustundagi sotuvlar yig‘indisini top”</p>
              <button onClick={() => onSendMessage('A ustundagi sonlarning yig‘indisi uchun formula yaratib ber')}>SUM formulasini yarat</button>
              <button onClick={() => onSendMessage('Agar D2 100 dan katta bo‘lsa Ha, bo‘lmasa Yo‘q formulasi kerak')}>IF formulasini yarat</button>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div 
              key={index} 
              className={`message ${msg.role === 'user' ? 'user-message' : 'assistant-message'}`}
            >
              {msg.content}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <form onSubmit={handleSubmit} className="message-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Excel bo‘yicha savol yozing..."
          aria-label="Message input"
        />
        <button type="submit" aria-label="Send message">
          <FiSend />
        </button>
      </form>
    </div>
  );
};

export default ChatInterface;
