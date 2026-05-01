# BrainCache – Second Brain Memory System  
### 👩‍💻 Developed by Roshni Maheshwari  
🔗 Live Demo: https://braincache-second-brain-memory-api.onrender.com  

## Project Overview  
In today’s digital era, individuals manage a large amount of personal information such as notes, ideas, and tasks. However, retrieving this information efficiently remains a major challenge.  

Traditional systems rely on keyword-based search, which often fails when users do not remember the exact words used during storage.  

BrainCache addresses this problem using AI and NLP-based semantic search, enabling users to retrieve information based on meaning rather than exact keywords.  

## Key Objectives  
- Develop an intelligent memory storage system  
- Implement semantic search using AI techniques  
- Provide fast and accurate retrieval of data  
- Enable tagging and pinning for better organization  
- Design a simple and user-friendly interface  

## System Modules  
- Memory Storage  
- Semantic Search  
- Tagging System  
- Pin Feature  
- User Session Management  

## Tech Stack  
**Backend:** Python, FastAPI  
**Database:** MongoDB   
**Frontend:** HTML, CSS, JavaScript  
**AI & NLP:** Sentence Transformers (via Hugging Face Inference API for scalable and memory-efficient deployment)  

## How to Run Locally  

**1. Clone the repository**
```bash
git clone https://github.com/roshni-maheshwari13/BrainCache---Second-Brain-Memory-API.git
cd BrainCache---Second-Brain-Memory-API
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Setup Environment Variables (.env)**
```env
MONGO_URI=your_mongodb_connection_string
HUGGINGFACE_API_KEY=your_huggingface_token
```

**4. Run the server**
```bash
uvicorn main:app --reload
```

## Features  
- Semantic search (meaning-based retrieval)  
- Tagging and filtering system  
- Pin important memories  
- Memory summary generation  
- Fast and efficient performance  

## Future Scope  
- Mobile application  
- Voice-based input  
- Multi-language support  

## Author  
Roshni Maheshwari

## Conclusion  
BrainCache acts as a “second brain” by enhancing memory management through AI-powered semantic search. It reduces dependency on exact keywords and improves productivity by enabling intelligent and efficient data retrieval.  

"Your memory is limited, but your second brain isn’t."
