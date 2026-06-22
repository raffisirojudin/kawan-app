"""
Kawan - Chatbot AI dengan Memori Permanen
Streamlit app: ngobrol dengan AI yang mengingat riwayat chat dan
fakta-fakta penting tentang kamu lintas sesi, memakai Gemini API + Supabase.
"""

from datetime import datetime

import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client

# ============================================================
# KONFIGURASI HALAMAN & KONSTANTA
# ============================================================
st.set_page_config(page_title="Kawan", page_icon="🌱", layout="centered")

APP_VERSION = "v1.0"
MODEL_NAME = "gemini-2.5-flash-lite"
RECENT_MESSAGES_LIMIT = 20


# ============================================================
# SECRETS
# ============================================================
def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
APP_PASSWORD = get_secret("APP_PASSWORD")

if not (GEMINI_API_KEY and SUPABASE_URL and SUPABASE_KEY):
    st.title("🌱 Kawan")
    st.error("⚠️ Setup belum lengkap. App ini butuh 3 secret berikut diisi dulu:")
    st.code(
        'GEMINI_API_KEY = "key-gemini-kamu"\n'
        'SUPABASE_URL = "https://xxxx.supabase.co"\n'
        'SUPABASE_KEY = "anon-key-dari-supabase"',
        language="toml",
    )
    st.caption("Isi lewat Settings → Secrets (Streamlit Cloud) atau .streamlit/secrets.toml (lokal). Lihat README untuk panduan lengkap.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# PROTEKSI PASSWORD (opsional -- sangat disarankan untuk app ini)
# ============================================================
if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🌱 Kawan")
        st.caption("🔒 Aplikasi ini dilindungi password.")
        pwd_input = st.text_input("Masukkan password", type="password", key="app_password_gate")
        if st.button("Masuk", type="primary"):
            if pwd_input == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Password salah, coba lagi.")
        st.stop()


# ============================================================
# HELPER: GEMINI
# ============================================================
def call_gemini(prompt, max_output_tokens=500, temperature=0.7):
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_output_tokens),
    )
    return response.text


def handle_gemini_error(e):
    msg = str(e).lower()
    if "resource_exhausted" in msg or "429" in msg or "quota" in msg:
        st.error("⏳ Kuota Gemini habis untuk saat ini. Coba lagi beberapa saat lagi.")
    elif "unavailable" in msg or "503" in msg:
        st.error("🔄 Server Gemini sedang sibuk. Coba lagi sebentar.")
    elif "api_key_invalid" in msg or "401" in msg or "403" in msg:
        st.error("🔑 API Key Gemini tidak valid. Cek lagi di Secrets.")
    else:
        st.error(f"Terjadi kesalahan: {e}")


PERSONALITY_PRESETS = {
    "Santai": "Gunakan bahasa santai dan akrab, seperti ngobrol sama teman dekat. Boleh pakai bahasa sehari-hari yang wajar.",
    "Formal": "Gunakan bahasa yang sopan, formal, dan terstruktur, seperti berbicara dengan orang yang dihormati.",
    "Jenaka": "Gunakan nada jenaka, ringan, dan suka bercanda, tapi tetap perhatian dan nggak berlebihan.",
    "Suportif": "Fokus jadi pendengar yang penuh empati dan suportif, validasi perasaan pengguna, dan beri semangat.",
}


def build_chat_prompt(user_name, memories, recent_messages, new_message, personality_instruction):
    memory_text = "\n".join(f"- {m['fact']}" for m in memories) if memories else "(belum ada catatan apapun)"
    system_instruction = (
        f"Kamu adalah Kawan, teman ngobrol AI untuk {user_name}. {personality_instruction} "
        f"Berikut hal-hal yang sudah kamu ingat tentang {user_name} dari percakapan-percakapan sebelumnya:\n"
        f"{memory_text}\n\n"
        "Gunakan catatan ini secara natural kalau memang relevan dengan obrolan saat ini -- jangan "
        "menyebutkannya secara kaku atau seperti membaca daftar. Selalu balas dalam Bahasa Indonesia."
    )
    history_lines = [
        f"{user_name if m['role'] == 'user' else 'Kawan'}: {m['content']}" for m in recent_messages
    ]
    history_text = "\n".join(history_lines)
    return f"{system_instruction}\n\nRiwayat percakapan:\n{history_text}\n\n{user_name}: {new_message}\nKawan:"


def extract_fact(user_message, assistant_reply):
    prompt = (
        "Dari potongan percakapan berikut, apakah ada SATU fakta penting tentang pengguna yang layak "
        "diingat jangka panjang (contoh: nama, pekerjaan, hobi, preferensi, tujuan, hubungan, tanggal penting)? "
        "Tulis fakta itu singkat dan padat (maksimal 15 kata) dalam Bahasa Indonesia. "
        "Kalau tidak ada fakta baru yang layak diingat, jawab TEPAT: TIDAK_ADA\n\n"
        f"Pengguna: {user_message}\nAsisten: {assistant_reply}"
    )
    try:
        result = call_gemini(prompt, max_output_tokens=60, temperature=0.2).strip()
    except Exception:
        return None
    if not result or result.upper().startswith("TIDAK_ADA"):
        return None
    return result


# ============================================================
# HELPER: SUPABASE (database permanen)
# ============================================================
def handle_db_error(e):
    st.error(f"⚠️ Gagal mengakses database: {e}")


def load_messages(user_id):
    try:
        response = supabase.table("messages").select("*").eq("user_id", user_id).order("created_at").execute()
        return response.data or []
    except Exception as e:
        handle_db_error(e)
        return []


def save_message(user_id, role, content):
    try:
        supabase.table("messages").insert({"user_id": user_id, "role": role, "content": content}).execute()
    except Exception as e:
        handle_db_error(e)


def load_memories(user_id):
    try:
        response = supabase.table("memories").select("*").eq("user_id", user_id).order("created_at").execute()
        return response.data or []
    except Exception as e:
        handle_db_error(e)
        return []


def save_memory(user_id, fact):
    try:
        response = supabase.table("memories").insert({"user_id": user_id, "fact": fact}).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        handle_db_error(e)
        return None


def update_memory(memory_id, new_fact):
    try:
        supabase.table("memories").update({"fact": new_fact}).eq("id", memory_id).execute()
    except Exception as e:
        handle_db_error(e)


def delete_memory(memory_id):
    try:
        supabase.table("memories").delete().eq("id", memory_id).execute()
    except Exception as e:
        handle_db_error(e)


def delete_all_messages(user_id):
    try:
        supabase.table("messages").delete().eq("user_id", user_id).execute()
    except Exception as e:
        handle_db_error(e)


def delete_all_memories(user_id):
    try:
        supabase.table("memories").delete().eq("user_id", user_id).execute()
    except Exception as e:
        handle_db_error(e)


# ============================================================
# HEADER
# ============================================================
st.title("🌱 Kawan")
st.caption("Teman ngobrol AI yang nggak gampang lupa.")

badge_col1, badge_col2, badge_col3 = st.columns(3)
with badge_col1:
    st.badge("Memori Permanen", icon="🧠", color="green")
with badge_col2:
    st.badge("Gemini API", icon="✨", color="blue")
with badge_col3:
    st.badge(APP_VERSION, icon="🌱", color="gray")

st.divider()


# ============================================================
# SIDEBAR: IDENTITAS & MANAJEMEN MEMORI
# ============================================================
with st.sidebar:
    st.markdown("### 🌱 Kawan")
    st.caption("Chatbot dengan memori permanen")
    st.divider()

    st.header("👤 Identitas")
    user_name = st.text_input(
        "Nama kamu",
        key="user_name_input",
        placeholder="misal: Budi",
        help="Dipakai untuk memisahkan riwayat & memori tiap orang. Bukan sistem login asli -- pakai nama yang konsisten.",
    )
    st.caption("⚠️ Ini bukan login sungguhan. Untuk privasi penuh, aktifkan `APP_PASSWORD` di Secrets.")

    st.divider()
    st.header("🎭 Kepribadian")
    personality_choice = st.selectbox(
        "Gaya ngobrol Kawan", list(PERSONALITY_PRESETS.keys()), key="personality_choice"
    )

    if user_name:
        if st.session_state.get("loaded_user_name") != user_name:
            st.session_state.chat_history = load_messages(user_name)
            st.session_state.memories = load_memories(user_name)
            st.session_state.loaded_user_name = user_name

        st.divider()
        st.header("🧠 Yang aku ingat")
        memories = st.session_state.get("memories", [])
        if not memories:
            st.caption("Belum ada catatan. Ngobrol dulu, nanti otomatis terisi.")
        else:
            for mem in memories:
                is_editing = st.session_state.get(f"editing_{mem['id']}", False)

                if is_editing:
                    new_fact_text = st.text_input(
                        "Edit fakta", value=mem["fact"], key=f"edit_input_{mem['id']}", label_visibility="collapsed"
                    )
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Simpan", key=f"save_mem_{mem['id']}", use_container_width=True):
                            update_memory(mem["id"], new_fact_text)
                            mem["fact"] = new_fact_text
                            st.session_state[f"editing_{mem['id']}"] = False
                            st.rerun()
                    with col_cancel:
                        if st.button("Batal", key=f"cancel_mem_{mem['id']}", use_container_width=True):
                            st.session_state[f"editing_{mem['id']}"] = False
                            st.rerun()
                else:
                    col_fact, col_edit, col_del = st.columns([4, 1, 1])
                    with col_fact:
                        st.caption(f"• {mem['fact']}")
                    with col_edit:
                        if st.button("✏️", key=f"edit_btn_{mem['id']}", help="Edit fakta ini"):
                            st.session_state[f"editing_{mem['id']}"] = True
                            st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"del_mem_{mem['id']}", help="Lupakan fakta ini"):
                            delete_memory(mem["id"])
                            st.session_state.memories = [m for m in memories if m["id"] != mem["id"]]
                            st.rerun()

        st.divider()
        st.header("⚠️ Zona Berbahaya")
        confirm_clear_chat = st.checkbox("Saya yakin mau hapus semua riwayat chat", key="confirm_clear_chat")
        if st.button("🧹 Hapus Riwayat Chat", disabled=not confirm_clear_chat, use_container_width=True):
            delete_all_messages(user_name)
            st.session_state.chat_history = []
            st.rerun()

        confirm_clear_memory = st.checkbox("Saya yakin mau hapus semua memori", key="confirm_clear_memory")
        if st.button("🗑️ Lupakan Semua Tentang Saya", disabled=not confirm_clear_memory, use_container_width=True):
            delete_all_memories(user_name)
            st.session_state.memories = []
            st.rerun()


# ============================================================
# AREA CHAT UTAMA
# ============================================================
if not user_name:
    st.info("👋 Masukkan nama kamu di sidebar dulu buat mulai ngobrol.")
    st.stop()

for msg in st.session_state.get("chat_history", []):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

new_message = st.chat_input(f"Ngobrol sama Kawan, {user_name}...")

if new_message:
    save_message(user_name, "user", new_message)
    st.session_state.chat_history.append({"role": "user", "content": new_message})
    with st.chat_message("user"):
        st.write(new_message)

    recent = st.session_state.chat_history[-RECENT_MESSAGES_LIMIT:-1]
    personality_instruction = PERSONALITY_PRESETS[personality_choice]
    prompt = build_chat_prompt(user_name, st.session_state.get("memories", []), recent, new_message, personality_instruction)

    try:
        with st.chat_message("assistant"):
            with st.spinner("Kawan sedang mengetik..."):
                reply = call_gemini(prompt, max_output_tokens=500)
            st.write(reply)
        save_message(user_name, "assistant", reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})

        fact = extract_fact(new_message, reply)
        if fact:
            mem_row = save_memory(user_name, fact)
            if mem_row:
                st.session_state.memories.append(mem_row)
                st.rerun()
    except Exception as e:
        handle_gemini_error(e)


# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(f"🌱 Kawan {APP_VERSION} · Ditenagai Gemini API & Supabase · Proyek pembelajaran AI API")
