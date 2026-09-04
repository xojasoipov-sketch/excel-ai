# ExcelYordamchi AI

O‘zbek, rus va ingliz tillarida Excel formulalarini yaratadigan, faylni tahlil qiladigan
**web SaaS** va Telegram bot. Asos: [ExcelFlow](https://github.com/parthvadhadiya/ExcelFlow),
MIT litsenziyasi asosida moslashtirilgan.

## Mahsulot tuzilishi

| Bo‘lim | Kirish huquqi |
|---|---|
| Formula kutubxonasi (24 shablon) + Formula Test | Hammaga, hisobsiz ham, cheksiz bepul (AI ishlatmaydi) |
| Fayl yuklab AI bilan ishlash, faylsiz formula so‘rash | Hisob kerak. Bepul reja: kuniga `FREE_DAILY_LIMIT` (odatda 5) so‘rov |
| Cheksiz AI | Pro — $5/oy (Stripe), yoki promokod, yoki `OWNER_EMAIL` egasi |
| `/admin` | Faqat `OWNER_EMAIL` egasi |

## Arxitektura

- **Backend** — FastAPI. Bitta servis ham API'ni, ham yig‘ilgan React SPA'ni tarqatadi
  (`frontend/dist`), shuning uchun sayt va API bir origin'da bo‘ladi.
- **Auth + DB** — Supabase (Google OAuth va email/parol, Postgres).
  Backend Supabase access-token'ni tekshiradi va `profiles` jadvalidan reja/huquqni oladi.
- **To‘lov** — Stripe Checkout + webhook. Kalitlar sozlanmagan bo‘lsa, sayt ishlaydi,
  faqat karta orqali to‘lov o‘chirilgan bo‘lib turadi (100% promokodlar ishlaydi).
- **Promokodlar** — 100% kod DB'da to‘g‘ridan-to‘g‘ri Pro beradi; qismli chegirma
  (1–99%) Stripe kuponiga aylanib, keyingi to‘lovda qo‘llanadi.

Jadvalar: `profiles`, `uploads`, `usage_events`, `payments`, `promo_codes`,
`promo_redemptions`, `admin_settings`, `app_config`.

## Mahalliy ishga tushirish

1. `backend/.env.example` → `backend/.env`, `frontend/.env.example` → `frontend/.env`
   nusxa olib to‘ldiring (kalitlar quyida).
2. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
3. Frontend: `cd frontend && npm install && npm run dev` (`http://localhost:5173`)
4. Telegram bot (ixtiyoriy): `.env`ga `TELEGRAM_BOT_TOKEN` qo‘shib `python telegram_bot.py`.

## Kalitlar (`backend/.env`)

| Kalit | Qayerdan |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API |
| `OWNER_EMAIL` | Cheksiz bepul + admin huquqi shu emailga beriladi |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` | Asosiy AI provayder (B.AI / DeepSeek) |
| `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL` | Zaxira AI provayder (Google AI Studio) — asosiysi ishlamasa avtomatik shunga o‘tadi. Env o‘rniga Supabase `app_config` jadvalidan ham o‘qiladi (redeploy’siz almashtirish uchun). |
| `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard (ixtiyoriy) |
| `CARD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SITE_URL` | Saytning ommaviy manzili (Stripe redirect va CORS uchun) |

Frontend (`frontend/.env`, brauzerga ketadi — maxfiy kalit qo‘ymang):
`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, (dev uchun) `VITE_API_URL`.

## Deploy (Render)

`render.yaml` blueprint mavjud. Qo‘lda sozlaganda:

- **Build:** `pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build`
- **Start:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/api/health`
- Barcha maxfiy kalitlarni Render → Environment bo‘limiga qo‘shing.

Stripe webhook manzili: `https://<sayt>/api/billing/webhook`
(hodisalar: `customer.subscription.*`, `checkout.session.completed`, `invoice.paid`).

## Desktop (Electron)

Desktop varianti ham saqlangan: `npm run desktop` (ishga tushirish) yoki
`npm run dist:win` (paket). Web build `/assets/...`, desktop build `./assets/...`
yo‘llardan foydalanadi — buni `BUILD_TARGET=desktop` boshqaradi.

API kalitlar hech qachon GitHub’ga yuborilmaydi (`.env` gitignore'da).

---

<div align="center">

![ExcelFlow Logo](https://img.shields.io/badge/ExcelFlow-AI%20Excel%20Assistant-blue?style=for-the-badge)

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

An interactive web application for managing and analyzing Excel sheets using OpenAI's GPT models. This app allows users to ask natural language questions about their Excel file, perform updates, summarize data, and more — all with the help of a conversational AI.

**If you find this project useful, please consider giving it a star ⭐ on GitHub!**

---

## 🚀 Features

* **Chat with your Excel Sheet:**
  Ask questions, filter data, make edits, and get summaries in plain English.

* **Read & Update Cells/Ranges:**
  Read individual cells or ranges, update data, insert/delete rows and columns, and more.

* **Summarization:**
  Quickly get sums, averages, mins, and maxes for any range of numbers.

* **Find & Replace:**
  Perform powerful find-and-replace operations over the whole sheet or just a selected area.

* **OpenAI GPT-4o Integration:**
  Advanced reasoning and understanding through OpenAI's GPT models and function calling.

* **Real-time Updates:**
  See changes to your Excel file in real-time as the AI makes modifications.

* **Modern Web Interface:**
  React-based frontend with a responsive design for a great user experience.

* **WebSocket Communication:**
  Real-time bidirectional communication between the frontend and backend.

---

## 🏗️ Architecture

The application is split into two main components:

### Backend (FastAPI)
- RESTful API for file uploads and data retrieval
- WebSocket server for real-time communication
- Excel manipulation utilities
- OpenAI integration for natural language processing

### Frontend (React)
- Modern React application built with Vite
- Interactive spreadsheet view using React Data Grid
- Real-time chat interface
- File upload functionality

---

## 🛠️ Setup

### Backend Setup

1. **Navigate to the backend directory:**

   ```bash
   cd backend
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Create and fill your `.env` file in the backend directory:**

   ```ini
   OPENAI_API_KEY=your_openai_key
   ```

4. **Run the backend server:**

   ```bash
   uvicorn app.main:app --reload 
   OR 
   python -m uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup

1. **Navigate to the frontend directory:**

   ```bash
   cd frontend
   ```

2. **Install dependencies:**

   ```bash
   npm install
   ```

3. **Run the development server:**

   ```bash
   npm run dev
   ```

4. **Open your browser and navigate to:**
   
   ```
   http://localhost:3000
   ```

## 📝 Usage

1. Upload an Excel file through the web interface
2. View your spreadsheet in the main area
3. Use the chat interface on the right to interact with the AI
4. Ask questions or give commands about your data
5. Watch as changes are reflected in real-time in the spreadsheet view

### Example Commands

- "What's the sum of sales in column C?"
- "Find all cells containing 'Product X' and replace with 'Product Y'"
- "Insert a new row at position 5"
- "Calculate the average of cells B5:B15"
- "Add a total row at the bottom of the sheet"
- "Sort column D in descending order"
- "Highlight all cells with values greater than 100"

## 📊 Demo

### Video Demonstrations

Check out these video demonstrations of ExcelFlow in action:

![ExcelFlow Demo](docs/videos/demo1.gif)

## 🔧 Advanced Configuration

### Environment Variables

**Backend (.env file):**

```ini
OPENAI_API_KEY=your_openai_key
DEBUG=True  # Optional for verbose logging
```

### Customizing the AI Model

You can change the OpenAI model used by modifying the `model` parameter in `backend/app/agent.py`:

```python
response = self.client.chat.completions.create(
    model="gpt-4o",  # Change to your preferred model
    messages=all_messages,
    tools=self.tools,
    tool_choice="auto"
)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👨‍💻 Author

**Parth Vadhadiya**

- Website: [https://parthvadhadiya.netlify.app/](https://parthvadhadiya.netlify.app/)
- LinkedIn: [https://www.linkedin.com/in/parth-vadhadiya/](https://www.linkedin.com/in/parth-vadhadiya/)
- GitHub: [@parthvadhadiya](https://github.com/parthvadhadiya)

---

<div align="center">

### If you found this project helpful, please consider giving it a star! ⭐

</div>
