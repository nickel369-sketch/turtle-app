import io, json, base64
import streamlit as st
import anthropic
from PIL import Image, ImageOps

st.set_page_config(page_title="Turtle Shell Check", page_icon="🐢")

MODEL = "claude-sonnet-5-5"
MAX_SCANS = 10  # per visitor session; protects your API budget

PROMPT = """You are screening photos of a turtle shell for visible signs of shell rot.
You will get one or two photos: the top shell (carapace) and optionally the underside (plastron).
Judge ONLY what is visible. Do not answer "uncertain" just because a part of the shell is not
shown, or because you cannot rule out tiny changes.

Choose one verdict:
- "rot": you can see one or more clear signs: pitting, ulcerated or eroded areas, soft or
  crumbling patches, exposed bone, discharge, or lifted/peeling scutes over discolored areas.
- "healthy": the visible shell surface looks intact with none of the signs above. Glare, wet
  shine, dried mud, normal scute seams and normal growth rings are NOT signs of rot.
- "uncertain": use ONLY if (a) the photos are too blurry, dark or small to see the shell surface,
  (b) they do not show a turtle shell, or (c) you can point to a specific suspicious area but
  cannot tell whether it is rot or something harmless (for example a chalky white patch).

Respond with ONLY a JSON object, no other text:
{"verdict": "rot" or "healthy" or "uncertain", "image_quality": "good" or "fair" or "poor",
 "visible_signs": "short description",
 "not_visible": "what a better photo would show, or none",
 "alternative_explanations": "short"}"""


@st.cache_resource
def get_client():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"].strip())


def to_b64(file):
    img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")  # fixes phone rotation
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)  # re-saving also drops GPS/location data
    return base64.standard_b64encode(buf.getvalue()).decode()


def analyze(files):
    content = []
    for label, f in files:
        content.append({"type": "text", "text": label})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": to_b64(f)}})
    content.append({"type": "text", "text": PROMPT})
    resp = get_client().messages.create(
        model=MODEL, max_tokens=2000,
        messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    return json.loads(text.strip().replace("```json", "").replace("```", ""))


st.title("🐢 Turtle Shell Check")
st.caption("A screening aid, not a diagnosis. A suspected case needs an exotics vet.")

with st.expander("Photo tips", expanded=True):
    st.write(
        "- Good light, no flash glare, shell dry if possible\n"
        "- Close enough to see the scutes, whole shell in frame\n"
        "- Take a **top** photo, and if you can, an **underside** photo too"
    )

if "scans" not in st.session_state:
    st.session_state.scans = 0

top = st.file_uploader("1. Top of shell (required)", type=["jpg", "jpeg", "png", "webp"], key="top")
under = st.file_uploader("2. Underside (recommended)", type=["jpg", "jpeg", "png", "webp"], key="under")

if top and st.button("Check shell", type="primary"):
    if st.session_state.scans >= MAX_SCANS:
        st.warning("Scan limit reached for this session.")
    else:
        files = [("Photo 1: top of the shell (carapace)", top)]
        if under:
            files.append(("Photo 2: underside (plastron)", under))
        with st.spinner("Looking at the shell..."):
            try:
                r = analyze(files)
                st.session_state.scans += 1
            except Exception:
                st.error("Something went wrong. Please try again.")
                st.stop()

        v = r["verdict"]
        if v == "rot":
            st.error("Possible shell rot. Please see an exotics vet.")
        elif v == "uncertain":
            st.warning("Not sure. See a vet, or retake the photos using the tips below.")
        else:
            st.success("No concerning signs seen in these photos. Keep monitoring.")

        st.write(f"**Photo quality:** {r['image_quality']}")
        st.write(f"**What I see:** {r['visible_signs']}")
        if r["not_visible"].strip().lower() != "none":
            st.write(f"**A better photo would show:** {r['not_visible']}")
        st.write(f"**Could also be:** {r['alternative_explanations']}")
        if not under:
            st.info("Adding an underside photo usually gives a more reliable result.")
        st.caption("This tool can miss problems. When in doubt, see a vet.")

st.divider()
st.caption("Photos are sent to an AI model for analysis and are not saved by this app.")
