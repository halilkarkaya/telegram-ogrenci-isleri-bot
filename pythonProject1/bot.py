import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import UnstructuredExcelLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
load_dotenv()

persist_directory = "db"


def veritabanıVarMı():
    # Eğer veritabanı zaten varsa, onu yükle
    if os.path.exists(persist_directory):
        print("Mevcut veritabanı yükleniyor...")
        chroma = Chroma(
            persist_directory=persist_directory,
            embedding_function=GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        )
    else:
        print("Yeni veritabanı oluşturuluyor...")
        loader = UnstructuredExcelLoader(file_path="soru_cevaplar.xlsx", mode="elements")
        documents = loader.load()
        documents = filter_complex_metadata(documents)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        chroma = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=persist_directory
        )



    retriever = RunnableLambda(chroma.similarity_search).bind(k=2)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)

    message = """
    lütfen sadece sana verilen belgeden cevaplar oluştur bunun dışında bir soru soruluyorsa bilmiyorum falan de yapabileceğin şeyler hakkında 2 satır bir bilgi ver uzun uzun her şeyi getirme
    Cevabı türkçe ve olabildiğince kısa ver.  
    İnsanlara yardımcı olmak için oluşturuldun buna göre cevaplar ver.
    Görsellik kat biraz ve daha samimi ol.

    {question}

    Context:
    {context}
    """

    prompt = ChatPromptTemplate.from_messages([("human", message)])
    rag_chain = {"context": retriever, "question": RunnablePassthrough()} | prompt | llm

    return rag_chain



rag_chain = veritabanıVarMı()


def get_rag_response(question):
    try:
        response = rag_chain.invoke(question)
        return str(response.content)
    except Exception as e:
        return f"Bir hata oluştu: {str(e)}"


# Telegram Bot API Key
telegram_token = os.getenv("TELEGRAM_API_KEY")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    print(f"Gelen mesaj: {user_message}")

    try:
        # RAG zinciri üzerinden soruyu yanıtla
        bot_reply = get_rag_response(user_message)
    except Exception as e:
        bot_reply = f"Lan bi bok oldu: {e}"

    await update.message.reply_text(bot_reply)



app = ApplicationBuilder().token(telegram_token).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()