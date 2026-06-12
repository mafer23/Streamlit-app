# 🛡️ Marketplace Scam Detector (Colombia)

An AI-powered web application designed to detect and evaluate the risk of online scams in Colombian e-commerce platforms (such as Facebook Marketplace, Mercado Libre, and OLX). The app accepts raw descriptions, listing URLs, or screenshot uploads to run a comprehensive risk analysis using state-of-the-art LLMs.

---

## 💡 Why This Project Was Created

Digital marketplace fraud is a rapidly growing issue in Colombia. Scammers exploit local digital banking tools and consumer trust through predictable patterns. However, standard global safety algorithms often fail to detect these localized flags. 

This project was built to:
1. **Empower Buyers:** Give everyday users a quick, free tool to check suspicious listings before committing to a purchase.
2. **Detect Localized Patterns:** Target specific fraud vectors in Colombia, such as requests for upfront deposits via mobile wallets (Nequi, Daviplata, Dale), unrealistic pricing, fake urgency ("motivo viaje"), and refusing in-person meetings.
3. **Demonstrate AI Capabilities:** Show how structured JSON generation, web scraping, and multimodal computer vision (OCR/image analysis) can be combined to solve real-world problems.

---

## 🛠️ The Tech Stack

*   **Frontend & UI:** [Streamlit](https://streamlit.io/) — chosen for its ability to build fast, interactive, and modern web interfaces in Python.
*   **LLM Inference Engine:** [Groq Cloud LPU](https://groq.com/) — utilized for ultra-fast response times.
*   **AI Models:**
    *   **Llama 3.3 (70B):** Used for advanced text and URL metadata analysis.
    *   **Llama 4 Scout (Multimodal MoE):** Used for vision tasks (analyzing screenshots of listings and chat conversations).
*   **Web Scraping:** [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) & [Requests](https://requests.readthedocs.io/) — for parsing and cleaning listing metadata from public URLs.
*   **Secrets Management:** Built-in Streamlit Secrets configuration (`secrets.toml`) to ensure API Keys are kept safe and never leaked to version control.

---

## ✨ Features

-   **📝 Text Analysis:** Paste the listing description or chat messages directly.
-   **🔗 URL Extraction:** Input the listing link to automatically scrape details (supports general marketplaces; fallbacks gracefully when bots are blocked).
-   **📸 Multimodal Screenshot Scan:** Upload a screenshot of the listing or the WhatsApp conversation. The vision model reads the text and evaluates visual flags.
-   **📊 Risk Scoring:** Provides a clear hazard score (0–100), visual warning list, and localized security recommendations.

---

## 🚀 Installation & Local Setup

### 1. Get a Free Groq API Key
Sign up at [GroqCloud Console](https://console.groq.com/) and create a free API Key.

### 2. Project Configuration
Clone the repository and create a folder named `.streamlit` in the root directory. Inside it, create a file named `secrets.toml`:

```toml
GROQ_API_KEY = "your_actual_groq_api_key_here"
```
*(Note: A `.gitignore` is already included to make sure this file is never committed to GitHub).*

### 3. Install Dependencies
Ensure you have Python installed, then run:
```bash
pip install -r requirements.txt
```

### 4. Run the App
Launch the Streamlit server locally:
```bash
streamlit run app.py
```

---

## ☁️ Deployment

You can host this project for free on **Streamlit Community Cloud**:
1. Push the code to a GitHub repository.
2. Link your repository to [share.streamlit.io](https://share.streamlit.io/).
3. In **Advanced Settings** -> **Secrets**, paste your API Key:
   ```toml
   GROQ_API_KEY = "your_groq_api_key"
   ```
4. Click **Deploy** and your app will be online!
