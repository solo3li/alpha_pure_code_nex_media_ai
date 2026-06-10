# 🇪🇸 AI Spanish Teacher

A sophisticated AI-powered Spanish learning application that provides personalized language instruction with real-time voice interaction, bilingual support (Spanish-Arabic), and adaptive difficulty levels.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-yellow.svg)
![AI](https://img.shields.io/badge/AI-OpenRouter-purple.svg)

## 📸 Screenshots

<div align="center">
  <img src="images/Screenshot 2025-09-07 030405.png" alt="AI Spanish Teacher Interface" width="800"/>
  <p><em>Main interface showing level selection and voice interaction</em></p>
</div>

### 🎯 Level Selection Interface
- Clean, modern design with 6 Spanish proficiency levels
- Visual indicators for each level (A1-C2)
- Responsive grid layout

### 🎤 Voice Interaction
- Real-time voice recording with visual feedback
- Color-coded status ball (White/Red/Blue)
- Bilingual chat display (Spanish + Arabic)

### 🔊 Audio Learning
- Text-to-speech for Spanish pronunciation
- Level-appropriate vocabulary and grammar
- Continuous conversation flow

## ✨ Features

### 🎯 **Adaptive Learning Levels**
- **A1 (Beginner)**: Basic vocabulary, present tense only
- **A2 (Elementary)**: Common vocabulary, present/past tense
- **B1 (Intermediate)**: Varied vocabulary, multiple tenses
- **B2 (Upper Intermediate)**: Complex vocabulary, all tenses
- **C1 (Advanced)**: Sophisticated language, complex structures
- **C2 (Proficient)**: Native-level Spanish, advanced features

### 🎤 **Real-Time Voice Interaction**
- **Voice Recording**: Speak in any language
- **Speech-to-Text**: Automatic transcription using Whisper AI
- **Silence Detection**: Smart 3-second silence detection
- **Continuous Learning**: Seamless conversation flow

### 🌍 **Bilingual Support**
- **Spanish Responses**: AI generates level-appropriate Spanish
- **Arabic Translation**: Automatic Spanish-to-Arabic translation
- **Dual Display**: Both languages shown in chat interface
- **RTL Support**: Proper Arabic text rendering

### 🔊 **Audio Learning**
- **Text-to-Speech**: Spanish pronunciation using gTTS
- **Native Voice**: Authentic Spanish pronunciation
- **Level-Appropriate Speech**: Matches selected difficulty level

### 🎨 **Modern UI/UX**
- **Clean Interface**: Minimalist design with centered ball indicator
- **Visual States**: Color-coded status (White/Red/Blue)
- **Responsive Design**: Works on desktop and mobile
- **Real-Time Feedback**: Live sound/silence detection

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Microphone access
- Modern web browser

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-spanish-teacher.git
   cd ai-spanish-teacher
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_api_key_here
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:5000`

## 📋 Requirements

Create a `requirements.txt` file with the following dependencies:

```
Flask==2.3.3
python-dotenv==1.0.0
gTTS==2.4.0
openai-whisper==20231117
requests==2.31.0
```

## 🎮 How to Use

1. **Select Your Level**: Choose from A1 (Beginner) to C2 (Proficient)
2. **Start Learning**: Click "Start Call" to begin
3. **Speak Naturally**: Talk in Spainsh - the AI will respond in Spanish
4. **Learn Visually**: See both Spanish text and Arabic translation
5. **Listen & Learn**: Hear authentic Spanish pronunciation
6. **Continue Learning**: The conversation flows automatically

## 🔧 Technical Architecture

### Backend (Python/Flask)
- **Speech Recognition**: Whisper AI for accurate transcription
- **AI Responses**: OpenRouter API with level-specific prompts
- **Translation**: Automatic Spanish-to-Arabic translation
- **Text-to-Speech**: gTTS for Spanish audio generation

### Frontend (JavaScript/HTML/CSS)
- **Voice Recording**: WebRTC MediaRecorder API
- **Real-Time Audio Analysis**: Web Audio API for silence detection
- **Responsive UI**: Modern CSS with smooth animations
- **Bilingual Display**: RTL support for Arabic text

### AI Integration
- **OpenRouter API**: For AI responses and translations
- **Level-Specific Prompts**: Customized for each Spanish level
- **Context Awareness**: Maintains conversation context

## 🎯 Learning Levels Explained

| Level | Description | Vocabulary | Grammar | Example |
|-------|-------------|------------|---------|---------|
| **A1** | Beginner | Basic words | Present tense only | "Hola, ¿cómo estás?" |
| **A2** | Elementary | Common words | Present/past tense | "Ayer fui al cine" |
| **B1** | Intermediate | Varied vocabulary | Multiple tenses | "Si tuviera tiempo, viajaría" |
| **B2** | Upper Intermediate | Complex words | All tenses | "Habría sido mejor si hubieras venido" |
| **C1** | Advanced | Sophisticated | Complex structures | "A pesar de las circunstancias adversas" |
| **C2** | Proficient | Native-level | All features | "La idiosincrasia cultural es fascinante" |

## 🔧 Configuration

### Environment Variables
```bash
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Customization
- **Level Prompts**: Modify in `app.py` to adjust teaching style
- **UI Colors**: Update CSS variables in `static/style.css`
- **Audio Settings**: Adjust silence detection in `static/script.js`

## 📱 Browser Compatibility

- ✅ Chrome 80+
- ✅ Firefox 75+
- ✅ Safari 13+
- ✅ Edge 80+

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Whisper AI** for speech recognition
- **OpenRouter** for AI responses and translations
- **gTTS** for text-to-speech functionality
- **Flask** for the web framework

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yourusername/ai-spanish-teacher/issues) page
2. Create a new issue with detailed description
3. Contact: [your-email@example.com]

## 🚀 Future Enhancements

- [ ] Multiple language support
- [ ] Progress tracking
- [ ] Lesson plans
- [ ] Offline mode
- [ ] Mobile app
- [ ] Voice recognition improvements
- [ ] Custom vocabulary lists

---

**Made with ❤️ for Spanish learners worldwide**

*Start your Spanish learning journey today!* 🇪🇸
