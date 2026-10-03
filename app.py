import streamlit as st
import time
import json
from google import genai
from google.genai import types
from prompts import (
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
    SUMMARY_REQUEST_PROMPT
)
from twilio.rest import Client

st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗"
)

st.title("🥗 MacroSnap")
st.subheader("Your AI Nutrition Buddy")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)

client = get_gemini_client()

@st.cache_resource
def get_twilio_client():
    return Client(
        st.secrets["TWILIO_ACCOUNT_SID"],
        st.secrets["TWILIO_AUTH_TOKEN"]
    )

twilio_client = get_twilio_client()

def clean_whatsapp_text(text):
    return " ".join(text.split())

def send_whatsapp(to_number, user_name, summary):
    try:
        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary)
            },
            ensure_ascii=False
        )

        if not to_number.startswith("whatsapp:"):
            to_number = "whatsapp:" + to_number

        message = twilio_client.messages.create(
            to=to_number,
            from_=st.secrets["TWILIO_WHATSAPP_FROM"],
            content_sid=st.secrets["TWILIO_CONTENT_SID"],
            content_variables=content_variables
        )

        return True, message.sid
    except Exception as e:
        return False, str(e)

if "chat" not in st.session_state:
    st.session_state.chat = client.chats.create(
        model="gemini-3.5-flash",
        config={
            "system_instruction": SYSTEM_PROMPT
        }
    )

if "name" not in st.session_state:
    st.session_state.name = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "summary" not in st.session_state:
    st.session_state.summary = None

if "whatsapp_number" not in st.session_state:
    st.session_state.whatsapp_number = None

if st.session_state.summary:
    st.divider()
    st.subheader("📋 Your Latest Summary")
    st.write(st.session_state.summary)

if st.session_state.name is None:
    name = st.text_input("Enter your name")
    whatsapp_number = st.text_input("Enter your WhatsApp number")

    if st.button("Start MacroSnap"):
        if not name.strip():
            st.warning("Please enter your name.")
        elif not whatsapp_number.strip():
            st.warning("Please enter your WhatsApp number.")
        else:
            st.session_state.name = name
            st.session_state.whatsapp_number = whatsapp_number
            st.rerun()
else:
    st.success(
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    uploaded_photo = st.file_uploader(
        "📸 Upload a photo of your meal",
        type=["jpg", "jpeg", "png"]
    )

    question = st.chat_input(
        "Ask MacroSnap about your meal..."
    )

    if uploaded_photo:
        if st.button("Analyze Meal Photo"):
            st.image(
                uploaded_photo,
                caption="Your meal",
                width=400
            )

            photo_message = "📸 Meal photo uploaded"

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": photo_message
                }
            )

            with st.chat_message("user"):
                st.write(photo_message)
                st.image(uploaded_photo, width=400)

            image_bytes = uploaded_photo.getvalue()

            for attempt in range(3):
                try:
                    response = st.session_state.chat.send_message(
                        [
                            types.Part.from_bytes(
                                data=image_bytes,
                                mime_type=uploaded_photo.type
                            ),
                            "Analyze this meal photo. "
                            "Identify the food items and estimate "
                            "calories, protein, carbohydrates, and fat."
                        ]
                    )
                    break
                except Exception:
                    if attempt == 2:
                        st.error(
                            "Gemini is temporarily unavailable. "
                            "Please try again."
                        )
                        st.stop()
                    time.sleep(2)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response.text
                }
            )

            with st.chat_message("assistant"):
                st.write(response.text)

    if question:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": question
            }
        )

        with st.chat_message("user"):
            st.write(question)

        response = st.session_state.chat.send_message(question)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response.text
            }
        )

        with st.chat_message("assistant"):
            st.write(response.text)

    st.divider()
    st.subheader("📋 Nutrition Summary")

    if len(st.session_state.messages) > 0:
        if st.button("Generate Nutrition Summary"):
            conversation = ""

            for message in st.session_state.messages:
                conversation += (
                    message["role"]
                    + ": "
                    + message["content"]
                    + "\n"
                )

            summary_prompt = (
                SUMMARY_REQUEST_PROMPT
                + "\n\nHere is our conversation:\n"
                + conversation
            )

            with st.spinner(
                "Creating your nutrition summary..."
            ):
                response = st.session_state.chat.send_message(
                    summary_prompt
                )

            st.session_state.summary = response.text

            st.success("✅ Summary created!")
            st.write(st.session_state.summary)
    else:
        st.info(
            "Ask MacroSnap a question or upload a meal photo first."
        )

    st.divider()
    st.subheader("📱 WhatsApp")

    if st.session_state.summary:
        st.success("Your nutrition summary is ready.")

        if st.button("Send Summary to WhatsApp"):
            success, result = send_whatsapp(
                st.session_state.whatsapp_number,
                st.session_state.name,
                st.session_state.summary
            )

            if success:
                st.success("✅ Summary sent to WhatsApp!")
                st.write("Message SID:", result)
            else:
                st.error("❌ WhatsApp message could not be sent.")
                st.error(result)
    else:
        st.info("Generate your nutrition summary first.")