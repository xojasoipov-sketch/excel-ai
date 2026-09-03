import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import FileUpload from '../components/FileUpload';
import ExcelViewer from '../components/ExcelViewer';
import ChatInterface from '../components/ChatInterface';
import QuickChat from '../components/QuickChat';
import FormulaLibrary from '../components/FormulaLibrary';
import { apiFetch, websocketUrl } from '../lib/api';

function QuotaBanner({ message }) {
  return (
    <div className="quota-banner">
      <span>{message || 'Kunlik bepul limit tugadi.'}</span>
      <Link to="/billing" className="quota-banner-cta">Pro’ga o‘tish</Link>
    </div>
  );
}

/**
 * The signed-in product surface. Anonymous visitors get the Formula Library only
 * (it needs no AI and no account); the AI tabs require a session.
 */
const Workspace = ({ profile, session, onProfileRefresh }) => {
  const [clientId, setClientId] = useState(null);
  const [excelData, setExcelData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [socket, setSocket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [quotaMessage, setQuotaMessage] = useState(null);
  const isSignedIn = Boolean(session);
  const [landingTab, setLandingTab] = useState(isSignedIn ? 'upload' : 'library');
  const [workspaceTab, setWorkspaceTab] = useState('workbook');

  const fetchExcelData = useCallback(async (id) => {
    try {
      setExcelData(await apiFetch(`/excel/${id}`));
    } catch (err) {
      console.error('Error fetching Excel data:', err);
      setError('Jadval maʼlumotlarini yuklab bo‘lmadi.');
    }
  }, []);

  useEffect(() => {
    if (!clientId) return undefined;

    let ws;
    let cancelled = false;

    (async () => {
      const url = await websocketUrl(`/ws/${clientId}`);
      if (cancelled) return;
      ws = new WebSocket(url);

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'excel_update') {
          setExcelData({ data: data.data, metadata: data.metadata });
          return;
        }

        if (data.upgrade_required) {
          setQuotaMessage(data.response);
          return;
        }

        setMessages((prev) => [...prev, { role: 'assistant', content: data.response }]);
        if (data.excel_modified) fetchExcelData(clientId);
        onProfileRefresh?.();
      };

      ws.onerror = () => setError('Ulanishda xatolik. Sahifani yangilab ko‘ring.');
      setSocket(ws);
      fetchExcelData(clientId);
    })();

    return () => {
      cancelled = true;
      if (ws) ws.close();
    };
  }, [clientId, fetchExcelData, onProfileRefresh]);

  const handleFileUpload = async (file) => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await apiFetch('/upload', { method: 'POST', body: formData });
      setClientId(data.client_id);
    } catch (err) {
      console.error('Error uploading file:', err);
      setError(err.message || 'Faylni yuklab bo‘lmadi.');
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = (message) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError('Ulanish uzilgan. Sahifani yangilang.');
      return;
    }
    setMessages((prev) => [...prev, { role: 'user', content: message }]);
    socket.send(JSON.stringify({ message }));
  };

  const startNewWorkbook = () => {
    if (socket) socket.close();
    setClientId(null);
    setExcelData(null);
    setMessages([]);
    setError(null);
    setWorkspaceTab('workbook');
    setLandingTab('upload');
  };

  const requireAuthNotice = (
    <div className="auth-required">
      <h2>Bu bo‘lim uchun hisob kerak</h2>
      <p>Fayl yuklash va AI’dan formula so‘rash uchun tizimga kiring. Google akkaunt bilan bir bosishda bo‘ladi.</p>
      <Link to="/login" className="primary-btn">Kirish / Ro‘yxatdan o‘tish</Link>
      <p className="auth-required-hint">
        Formula kutubxonasi va Formula Test esa hisobsiz ham, cheksiz bepul ishlaydi.
      </p>
    </div>
  );

  if (!clientId) {
    return (
      <div className="landing">
        {quotaMessage && <QuotaBanner message={quotaMessage} />}
        <div className="landing-tabs">
          <button type="button" className={landingTab === 'upload' ? 'active' : ''} onClick={() => setLandingTab('upload')}>
            📁 Fayl yuklash
          </button>
          <button type="button" className={landingTab === 'quick' ? 'active' : ''} onClick={() => setLandingTab('quick')}>
            💬 Faylsiz so‘rash
          </button>
          <button type="button" className={landingTab === 'library' ? 'active' : ''} onClick={() => setLandingTab('library')}>
            📚 Formula kutubxonasi
          </button>
        </div>
        <div className="landing-body">
          {landingTab === 'upload' && (isSignedIn
            ? <FileUpload onFileUpload={handleFileUpload} loading={loading} error={error} />
            : requireAuthNotice)}
          {landingTab === 'quick' && (isSignedIn
            ? <QuickChat onQuotaExceeded={setQuotaMessage} onUsed={onProfileRefresh} />
            : requireAuthNotice)}
          {landingTab === 'library' && <FormulaLibrary />}
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      {quotaMessage && <QuotaBanner message={quotaMessage} />}
      <aside className="workspace-nav">
        <button className="new-workbook" onClick={startNewWorkbook}>＋ Yangi fayl</button>
        <nav>
          <span className={workspaceTab === 'workbook' ? 'nav-active' : ''} onClick={() => setWorkspaceTab('workbook')}>
            ▦ Ish kitobi
          </span>
          <span className={workspaceTab === 'library' ? 'nav-active' : ''} onClick={() => setWorkspaceTab('library')}>
            ◫ Shablonlar
          </span>
          <span className="nav-disabled" title="Tez orada">◌ AI tahlil</span>
        </nav>
        {profile?.quota && !profile.quota.unlimited && (
          <div className="quota-chip">
            Bugun qoldi: <b>{profile.quota.remaining}</b> / {profile.quota.limit}
          </div>
        )}
        <div className="file-help">Formulani ayting — AI uni yaratadi.</div>
      </aside>
      {workspaceTab === 'workbook' ? (
        <>
          <div className="excel-container">
            {excelData ? (
              <ExcelViewer data={excelData.data} metadata={excelData.metadata} />
            ) : (
              <div className="loading">Jadval yuklanmoqda...</div>
            )}
          </div>
          <div className="chat-sidebar">
            <ChatInterface messages={messages} onSendMessage={sendMessage} />
          </div>
        </>
      ) : (
        <div className="workspace-library-panel">
          <FormulaLibrary />
        </div>
      )}
    </div>
  );
};

export default Workspace;
