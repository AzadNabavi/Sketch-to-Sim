import os
import base64
from typing import TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import StateGraph, END
import json

# Ensure API keys are loaded via environment variables in production, NEVER hardcoded
# os.environ["GOOGLE_API_KEY"] = "YOUR_API_KEY_HERE"

class BEMState(TypedDict):
    image_path: str
    year: int
    category: str
    wwr: float
    roof_shape: str
    u_wall: float
    u_window: float
    rag_context: str
    error: str

class BEMAgenticWorkflow:
    """
    A LangGraph-based state machine that chains:
    1. Multimodal Vision (Facade Analysis)
    2. RAG Retrieval (PDF Building Codes)
    3. Structural Parameter Extraction
    """
    def __init__(self, pdf_dir="PDFs"):
        self.pdf_dir = pdf_dir
        
        # Initialize Gemini 1.5 Pro/Flash for Multimodal & Text (langchain integration)
        try:
            self.llm_vision = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.0)
            self.llm_text = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)
            self.vectorstore = self._init_rag()
        except Exception as e:
            print(f"Warning: API Key or Models not initialized. {e}")
            self.llm_vision = None
            self.llm_text = None
            self.vectorstore = None
            
        self.graph = self._build_graph()

    def _init_rag(self):
        """Initializes the Retrieval-Augmented Generation (RAG) vector database from PDFs."""
        if not os.path.exists(self.pdf_dir) or not os.listdir(self.pdf_dir):
            return None
        print("[LangChain] Indexing PDF Building Codes into FAISS VectorStore...")
        loader = PyPDFDirectoryLoader(self.pdf_dir)
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        return FAISS.from_documents(splits, embeddings)

    def analyze_facade(self, state: BEMState):
        """Node 1: Multimodal analysis of the building facade."""
        if not self.llm_vision:
            # Fallback for local testing without API key
            return {"year": 1990, "wwr": 0.25, "roof_shape": "Flat", "category": "MFH", "error": "No API Key"}

        try:
            with open(state["image_path"], "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
            prompt = (
                "You are an expert architect. Analyze this building facade image. "
                "Output strictly valid JSON with no markdown formatting containing: "
                "'wwr' (Window to wall ratio float), 'roof_shape' (Flat, Gable, or Hip), "
                "'category' (SFH, MFH, or Office), and 'construction_year' (integer estimate)."
            )
            
            # Construct Multimodal LangChain message
            msg = self.llm_vision.invoke([
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{encoded_string}"}
                ]}
            ])
            
            # Parse LLM JSON output
            raw_text = msg.content.strip().replace("```json", "").replace("```", "")
            data = json.loads(raw_text)
            
            return {
                "year": data.get("construction_year", 1990),
                "wwr": data.get("wwr", 0.25),
                "roof_shape": data.get("roof_shape", "Flat"),
                "category": data.get("category", "MFH")
            }
        except Exception as e:
            return {"error": str(e), "year": 1990, "wwr": 0.25, "roof_shape": "Flat", "category": "MFH"}

    def retrieve_u_values(self, state: BEMState):
        """Node 2: RAG retrieval to find legal U-Values based on construction year."""
        year = state.get("year", 1990)
        
        # Base Fallbacks
        u_wall, u_window = 1.2, 1.5
        if year < 1978: u_wall, u_window = 1.4, 2.8
        elif year < 1995: u_wall, u_window = 0.6, 1.8
        else: u_wall, u_window = 0.28, 1.3

        if not self.vectorstore or not self.llm_text:
            return {"u_wall": u_wall, "u_window": u_window, "rag_context": "Fallback values used."}
            
        try:
            # Query the FAISS VectorStore
            query = f"What are the standard U-Values for exterior walls and windows for a building constructed in {year}?"
            docs = self.vectorstore.similarity_search(query, k=3)
            context = "\n".join([d.page_content for d in docs])
            
            # LangChain Prompting
            prompt = ChatPromptTemplate.from_template(
                "Based on the following building code context:\n{context}\n\n"
                "Extract the 'u_wall' and 'u_window' as floats for a building built in {year}. "
                "Output strictly JSON: {{\"u_wall\": float, \"u_window\": float}}"
            )
            
            chain = prompt | self.llm_text
            res = chain.invoke({"context": context, "year": year})
            
            raw_text = res.content.strip().replace("```json", "").replace("```", "")
            data = json.loads(raw_text)
            return {
                "u_wall": data.get("u_wall", u_wall), 
                "u_window": data.get("u_window", u_window),
                "rag_context": context[:200] + "..."
            }
        except Exception as e:
            return {"u_wall": u_wall, "u_window": u_window, "rag_context": f"RAG Error: {e}"}

    def _build_graph(self):
        """Constructs the LangGraph State Machine."""
        workflow = StateGraph(BEMState)
        
        # Add Nodes
        workflow.add_node("vision_analysis", self.analyze_facade)
        workflow.add_node("rag_retrieval", self.retrieve_u_values)
        
        # Define Edges
        workflow.set_entry_point("vision_analysis")
        workflow.add_edge("vision_analysis", "rag_retrieval")
        workflow.add_edge("rag_retrieval", END)
        
        return workflow.compile()

    def run(self, image_path: str):
        """Executes the full multimodal agent workflow."""
        return self.graph.invoke({"image_path": image_path})

# Example usage:
# agent = BEMAgenticWorkflow()
# result = agent.run("facade.jpg")
