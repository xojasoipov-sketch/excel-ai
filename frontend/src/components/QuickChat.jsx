import React, { useEffect, useRef, useState } from 'react';
import { FiSend } from 'react-icons/fi';
import { apiFetch } from '../lib/api';

/**
 * "Faylsiz so'rash" mode: the user describes their columns in words and gets a
 * formula back — no upload needed. Talks to the stateless POST /chat/no-file
 * endpoint (no tools, no file access), matching the product brief's "Chat rejimi".
 */
const QuickChat = ({ onQuotaExceeded, onUsed }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text) => {
    const nextMessages = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setLoading(true);
    setError(null);

    try {
      const data = await apiFetch('/chat/no-file', {
        method: 'POST',
        body: JSON.stringify({ messages: nextMessages }),
      });
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: data.response,
        excelFileBase64: data.excel_file_base64 || null,
      }]);
      onUsed?.();
    } catch (err) {
      console.error('QuickChat error:', err);
      if (err.upgradeRequired) {
        onQuotaExceeded?.(err.message);
        setError(err.message);
      } else {
        setError(err?.message || 'Xabar yuborilmadi. Qayta urinib ko‘ring.');
      }
    } finally {
      setLoading(false);
    }
  };

  const downloadExcelFile = (base64Data) => {
    const bytes = Uint8Array.from(atob(base64Data), (c) => c.charCodeAt(0));
    const blob = new Blob([bytes], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'formula_namuna.xlsx';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    send(text);
  };

  return (
    <div className="quick-chat">
      <div className="quick-chat-header">
        <h2>💬 Faylsiz formula so‘rash</h2>
        <p>Fayl yuklamasdan, jadvalingizni so‘z bilan tasvirlab formula so‘rang.</p>
      </div>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-chat">
            <strong>Masalan shunday yozing:</strong>
            <p>“A ustuni — ism, B ustuni — oylik, C ustuni — bo‘lim. IT bo‘limidagilarning o‘rtacha oyligini top.”</p>
            <button onClick={() => send('A — ism, B — oylik, C — bo‘lim ustunlari bor. IT bo‘limidagilarning o‘rtacha oyligini topadigan formula ber')}>
              Namuna so‘rovni yuborish
            </button>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role === 'user' ? 'user-message' : 'assistant-message'}`}>
              {msg.content}
              {msg.excelFileBase64 && (
                <button
                  type="button"
                  className="excel-download-btn"
                  onClick={() => downloadExcelFile(msg.excelFileBase64)}
                >
                  📥 Excel faylni yuklab olish (namuna jadval + formula)
                </button>
              )}
            </div>
          ))
        )}
        {loading && <div className="message assistant-message quick-chat-loading">AI javob yozmoqda…</div>}
        {error && <div className="quick-chat-error">{error}</div>}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="message-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Jadvalingizni so‘z bilan tasvirlab, formula so‘rang…"
          aria-label="Message input"
          disabled={loading}
        />
        <button type="submit" aria-label="Send message" disabled={loading}>
          <FiSend />
        </button>
      </form>
    </div>
  );
};

export default QuickChat;
