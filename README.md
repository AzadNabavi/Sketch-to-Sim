# Sketch-to-Sim: Agentic AI for Building Energy Modeling

Sketch-to-Sim is an end-to-end multimodal AI architecture that bridges **Computer Vision**, **Agentic RAG**, and **Geometrical Physics Simulation**. It automates the generation of compliant EnergyPlus 3D models from unstructured 2D floor plan images and building facades.

## 🏗️ Architecture Stack

This project was built to demonstrate Senior AI Engineering capabilities in production:

1. **Computer Vision (SegFormer):** 
   - Uses a fine-tuned SegFormer (`floorplan_vectorizer`) to segment walls, windows, and doors from raw 2D floor plan images.
   - Snaps pixel coordinates into a metric vector space using custom Shapely topological healing algorithms ("Slit Algorithm") to make them valid for 3D physics engines.

2. **Agentic RAG (LangChain & LangGraph):** 
   - Implements a state-machine workflow (`backend/bem_agent.py`) using **LangGraph**.
   - **Node 1 (Multimodal Vision):** Uses Generative AI (Gemini/GPT-4o) to analyze building facade images and extract architectural parameters (Window-to-Wall Ratio, Roof Shape, Construction Year).
   - **Node 2 (RAG VectorStore):** Uses LangChain and FAISS to search a local database of PDF building codes, retrieving the legally mandated U-Values for the extracted construction year.

3. **Physics Simulation (OpenStudio/EnergyPlus):** 
   - A Python-based `BEM_EnterpriseArchitect` engine extrudes the 2D Agentic data into a complete 3D Thermal Zone model using the OpenStudio SDK.
   - Automatically runs C++ EnergyPlus simulations (`energyplus.exe`) to calculate precise kW/h heating demands.

4. **Web Interface (FastAPI + Gradio/Vanilla JS):**
   - Served securely via **FastAPI**.
   - Generates interactive 3D HTML schematic overlays using Plotly to visualize energy loads.

## 🚀 Setup & Execution

### 1. Environment Configuration
Ensure your API keys are set in your environment (DO NOT hardcode them in the source code).
```bash
export GOOGLE_API_KEY="your-api-key"
# or OPENAI_API_KEY if switching the LangChain models
```

### 2. Install Dependencies
```bash
pip install fastapi uvicorn pydantic langchain langchain-google-genai langchain-community langgraph faiss-cpu PyPDF2 shapely opencv-python numpy
```

### 3. Run the Application
```bash
uvicorn backend.main:app --reload
```
Navigate to `http://localhost:8000/app` to access the interface.

## 📁 Repository Structure
* `/backend/bem_agent.py` - The LangGraph StateMachine and RAG logic.
* `/backend/main.py` - The FastAPI server and OpenStudio injection logic.
* `/backend/snap_zones_shapely.py` - Custom geometry healing algorithms.
* `/floorplan_vectorizer/` - The SegFormer Computer Vision module.
* `/frontend/` - The web application interface.
* `/PDFs/` - The local knowledge base of building energy codes for RAG.

---
*Developed by Azad Nabavi.*
