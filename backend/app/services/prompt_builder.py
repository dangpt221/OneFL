import json
from typing import List, Dict, Any, Optional
from app.config import settings


class PromptBuilder:
    """Builds highly specialized translation prompts with speaker context, glossary, and language rules."""

    @staticmethod
    def get_language_specific_rules(source_lang: str) -> str:
        lang = source_lang.lower()
        if lang in ["en", "english"]:
            return """
### QUY TẮC DỊCH TIẾNG ANH (ENGLISH -> VIETNAMESE):
1. ĐẠI TỪ XƯNG HÔ: Tuyệt đối KHÔNG dịch cứng nhắc I/You thành "Tôi/Bạn". Phải căn cứ vào BẢNG HỒ SƠ NHÂN VẬT & QUY TẮC XƯNG HÔ để dịch thành (Anh/Em, Chú/Cháu, Sếp/Em, Bố/Con...).
2. PHRASAL VERBS & IDIOMS: Dịch thoát ý theo tiếng Việt tự nhiên (VD: "break a leg" -> "chúc may mắn", "call it a day" -> "nghỉ tay thôi").
3. THUẬT NGỮ CHUYÊN NGÀNH: Giữ nguyên các từ kỹ thuật/công nghệ/tài chính phổ biến (VD: API, Backend, Scale, Frontend, Database, Cache).
"""
        elif lang in ["zh", "chinese", "zh-cn", "zh-tw"]:
            return """
### QUY TẮC ĐẶC BIỆT BẮT BUỘC KHI DỊCH TIẾNG TRUNG (CHINESE -> VIETNAMESE):
1. ĐẶC BIỆT CHÚ Ý GIỚI TÍNH & ĐẠI TỪ XƯNG HÔ (CỰC KỲ QUAN TRỌNG):
   - Trong tiếng Trung khẩu ngữ và nhận diện ASR, từ "tā" thường bị viết thành "他" (nam) dù nhân vật trong phim là NỮ ("她")!
   - BẮT BUỘC PHÂN TÍCH KỸ NGỮ CẢNH HỘI THOẠI để xác định giới tính nhân vật:
     * Khi nhân vật NỮ nói hoặc đối tượng được nhắc đến là NỮ (như Cố Vãn Chu - 顾晚舟, cô bé, bạn gái, cô gái, nữ sinh):
       TUYỆT ĐỐI KHÔNG dịch thành "anh ta", "anh ấy", "hắn"!
       PHẢI dịch là: "cô ấy", "em ấy", "cô ta", "cô", "em", "nàng".
     * Khi nhân vật NAM (như Mục Thần - 牧尘, nam sinh, thiếu niên): Dùng "cậu ấy", "anh ấy", "hắn", "cậu".
     * Xưng hô đối thoại nam - nữ đồng trang lứa: "tôi - cô", "cậu - tôi", "anh - em" tự nhiên.
     * Xưng hô với giáo viên (Thầy Lâm / 林老师): "Thầy - em / con".
     * Đối với kẻ địch / phản diện (Bạch Cốt Lâu / 白骨楼): "bọn chúng", "ngươi - ta", "mày - tao".

2. DỊCH SÁT NGHĨA BỐI CẢNH PHIM KHOA HỌC VIỄN TƯỞNG / CƠ GIÁP (MECHA SCI-FI):
   - Dịch chính xác ngữ cảnh hành động viễn tưởng, TUYỆT ĐỐI KHÔNG dịch nhầm sang nông nghiệp hay đời thường:
     * 垃圾星 (Lạp ky tinh) -> "Tinh cầu rác" hoặc "Hành tinh phế liệu" (KHÔNG dịch máy kéo).
     * 捡垃圾 (Kiểm lạp ky) -> "Nhặt phế liệu" / "Thu gom ve chai cơ giáp" / "Bới rác tinh cầu".
     * 飞行器 (Phi hành khí) -> "Phi hành khí" / "Tàu bay".
     * 机甲 (Cơ giáp) -> "Cơ giáp" / "Robot chiến đấu".
     * 超神机甲 -> "Cơ giáp Siêu Thần".
     * 星际学院 -> "Học viện Tinh tế".
     * 联邦 -> "Liên bang".
     * 精神力 -> "Tinh thần lực".
     * 圣金 -> "Thánh Kim" / "Quặng Thánh Kim".
     * 白骨楼 (hoặc ASR 白酷楼) -> "Bạch Cốt Lâu" (tổ chức phản diện).
     * 顾晚舟 -> "Cố Vãn Chu" (nhân vật NỮ).
     * 牧尘 -> "Mục Thần" (nhân vật NAM chính).
     * 林老师 -> "Thầy Lâm".
3. VĂN PHONG TỰ NHIÊN, THUẦN VIỆT, SÚC TÍCH:
   - Câu thoại ngắn gọn, gãy gọn, giàu biểu cảm, phù hợp với nhịp độ phim hoạt hình hành động.
"""
        elif lang in ["ja", "japanese"]:
            return """
### QUY TẮC DỊCH TIẾNG NHẬT (JAPANESE -> VIETNAMESE):
1. KÍNH NGỮ (KEIGO):
   - Sonkeigo/Kenjougo: Dịch với sắc thái trang trọng, thêm kính ngữ "Dạ / Thưa / Vâng / Kính gửi" phù hợp.
   - Tameguchi (Thân mật): Dịch tự nhiên, thân thiết giữa bạn bè/đồng trang lứa.
2. HẬU TỐ DANH XƯNG:
   - '-san' -> Anh / Chị / Bạn [Tên].
   - '-sensei' -> Thầy / Cô / Bác sĩ [Tên].
   - '-senpai' -> Tiền bối / Anh / Chị [Tên].
   - '-chan / -kun' -> Bé / Em / Cậu [Tên].
3. ĐẠI TỪ TỰ XƯNG & GỌI NGƯỜI KHÁC:
   - Watashi/Watakushi -> Tôi / Em / Mình.
   - Boku/Ore -> Tôi / Tao / Anh / Mình (tùy độ thân thiết).
   - Anata/Omae/Kimi -> Bạn / Cậu / Mày / Em.
"""
        elif lang in ["ko", "korean"]:
            return """
### QUY TẮC DỊCH TIẾNG HÀN (KOREAN -> VIETNAMESE):
1. KÍNH NGỮ (JONDAETMAL) vs THÂN MẬT (BANMAL):
   - Đuôi câu '-습니다 / -십니까 / -해요' -> Thể hiện sự tôn trọng, thêm "ạ / thưa / vâng".
   - Đuôi câu '-야 / -어 / -지' -> Xưng hô thân mật giữa bạn bè hoặc người lớn nói với trẻ nhỏ.
2. DANH XƯNG XÃ HỘI & GIA ĐÌNH:
   - Oppa (오빠) -> Anh (nữ gọi nam lớn tuổi thân thiết).
   - Hyung (형) -> Anh (nam gọi nam lớn tuổi).
   - Noona (누на) / Unnie (언니) -> Chị.
   - Sunbae (선배) -> Tiền bối.
   - Daepyo-nim (대표님) -> Giám đốc / Sếp.
"""
        else:
            return """
### NGUYÊN TẮC DỊCH CHUNG:
- Văn phong tự nhiên, thuần Việt, đúng ngữ cảnh đối thoại thực tế.
- Tuân thủ bảng hồ sơ nhân vật và quan hệ xưng hô.
"""

    @classmethod
    def format_speaker_and_relationship_rules(
        cls,
        speaker_profiles: Optional[Any],
        relationship_matrix: Optional[Any]
    ) -> str:
        """Transforms speaker profiles and relationship matrix into strict, imperative Vietnamese translation directives."""
        if not speaker_profiles and not relationship_matrix:
            return ""

        sections = []
        sections.append("### [1. BẢNG HỒ SƠ NHÂN VẬT & MA TRẬN XƯNG HÔ - BẮT BUỘC TUÂN THỦ 100% SÁT NGHĨA]")

        # A. Character Registry
        speakers_dict = {}
        if isinstance(speaker_profiles, dict):
            speakers_dict = speaker_profiles
        elif isinstance(speaker_profiles, list):
            for spk in speaker_profiles:
                tag = spk.get("speaker_tag", "")
                if tag:
                    speakers_dict[tag] = spk

        if speakers_dict:
            sections.append("\nA. DANH SÁCH NHÂN VẬT CHÍNH TRONG PHIM:")
            for tag, info in speakers_dict.items():
                name = info.get("display_name") or info.get("name") or tag
                orig = info.get("original_name") or ""
                orig_str = f" (Tên gốc Hán tự: {orig})" if orig else ""
                gender_raw = str(info.get("gender", "unknown")).lower()
                gender_str = "NAM" if gender_raw in ["male", "nam"] else ("NỮ" if gender_raw in ["female", "nu", "nữ"] else "AI / Robot" if gender_raw == "neutral" else "Chưa rõ")
                role = info.get("role") or "Nhân vật"
                tone = info.get("tone") or ""
                notes = info.get("notes") or ""

                line = f"- [{tag}] Tên: **{name}**{orig_str} | Giới tính: **{gender_str}** | Vai trò: {role}"
                if tone:
                    line += f" | Giọng điệu: {tone}"
                if notes:
                    line += f"\n  * LƯU Ý BẮT BUỘC: {notes}"
                sections.append(line)

        # B. Pronoun Relationship Matrix
        rel_list = []
        if isinstance(relationship_matrix, list):
            rel_list = relationship_matrix
        elif isinstance(relationship_matrix, dict):
            for key, val in relationship_matrix.items():
                src = val.get("source_speaker")
                tgt = val.get("target_speaker")
                if not src or not tgt:
                    if "_to_" in key:
                        parts = key.split("_to_")
                        src = parts[0]
                        tgt = parts[1]
                rel_list.append({
                    "source_speaker": src,
                    "target_speaker": tgt,
                    "self_pronoun": val.get("self_pronoun") or val.get("self") or "",
                    "target_pronoun": val.get("target_pronoun") or val.get("target") or "",
                    "relationship_type": val.get("relationship_type") or "Đối thoại",
                    "honorific_notes": val.get("honorific_notes") or ""
                })

        if rel_list:
            sections.append("\nB. QUY TẮC MA TRẬN XƯNG HÔ ĐỐI THOẠI (STRICT PRONOUN DIRECTIVES):")
            sections.append("Khi 2 nhân vật trò chuyện, ĐẠI TỪ BẮT BUỘC PHẢI KHỚP TUYỆT ĐỐI VỚI BẢN DỊCH:")
            for idx, r in enumerate(rel_list, 1):
                src_tag = r.get("source_speaker", "")
                tgt_tag = r.get("target_speaker", "")
                src_name = (speakers_dict.get(src_tag, {})).get("display_name") or (speakers_dict.get(src_tag, {})).get("name") or src_tag
                tgt_name = (speakers_dict.get(tgt_tag, {})).get("display_name") or (speakers_dict.get(tgt_tag, {})).get("name") or tgt_tag
                self_p = r.get("self_pronoun", "")
                tgt_p = r.get("target_pronoun", "")
                rel_type = r.get("relationship_type") or "Đối thoại"
                h_notes = r.get("honorific_notes") or ""

                rule_text = (
                    f"{idx}. CẶP: **{src_name} ({src_tag})** nói với **{tgt_name} ({tgt_tag})** [Quan hệ: {rel_type}]:\n"
                    f"   - Tự xưng (Đại từ ngôi 1 / '我'): BẮT BUỘC DỊCH THÀNH: **\"{self_p}\"**\n"
                    f"   - Gọi đối phương (Đại từ ngôi 2 / '你'): BẮT BUỘC DỊCH THÀNH: **\"{tgt_p}\"**"
                )
                if h_notes:
                    rule_text += f"\n   - Lưu ý văn cảnh: {h_notes}"
                sections.append(rule_text)

        # C. Dialogue Inference & Turn-Taking Rules
        sections.append("""
C. NGUYÊN TẮC SUY LUẬN ĐỐI THOẠI QUA LẠI KHI CÙNG MÃ SPEAKER:
1. TRÒ CHUYỆN QUA LẠI: Trong kịch bản phim, các câu phụ đề kế tiếp nhau thường là cuộc đối đáp luân phiên giữa 2 nhân vật (Turn-taking conversation).
2. XỬ LÝ KHI CÙNG MÃ SPEAKER_00: Do công nghệ nhận diện giọng nói tự động gán chung SPEAKER_00 cho nhiều câu thoại, BẠN PHẢI TỰ PHÂN TÍCH NGỮ CẢNH CÂU NÓI ĐỂ SUY LUẬN AI LÀ NGƯỜI NÓI VÀ AI LÀ NGƯỜI NGHE:
   - Ví dụ: Một bên hỏi - một bên trả lời, hoặc một bên xưng tên (VD: "Tôi tên Dạ Định Thiên" -> đối phương đáp "Linh Thất").
   - Khi đã nhận biết người nói là nhân vật nào, BẮT BUỘC áp dụng đúng cặp xưng hô ở mục B cho câu thoại đó!
3. CẤM KỴ:
   - TUYỆT ĐỐI KHÔNG dịch bừa bãi thành "ngươi - ta" trừ khi là cổ trang kiếm hiệp hoặc kẻ thù huyết chiến.
   - TUYỆT ĐỐI KHÔNG dùng đại từ nam giới ("anh ta", "hắn") để chỉ nhân vật NỮ!
""")

        return "\n".join(sections)

    @classmethod
    def format_glossary_rules(cls, glossary: Optional[Any]) -> str:
        """Transforms glossary terms into strict, mandatory replacement rules."""
        if not glossary:
            return ""

        terms_list = []
        if isinstance(glossary, dict):
            for k, v in glossary.items():
                if isinstance(v, dict):
                    terms_list.append({
                        "source": k,
                        "target": v.get("target_term") or v.get("target") or "",
                        "note": v.get("context_note") or ""
                    })
                else:
                    terms_list.append({"source": k, "target": str(v), "note": ""})
        elif isinstance(glossary, list):
            for item in glossary:
                if isinstance(item, dict):
                    src = item.get("source_term") or item.get("source") or ""
                    tgt = item.get("target_term") or item.get("target") or ""
                    note = item.get("context_note") or item.get("note") or ""
                    if src and tgt:
                        terms_list.append({"source": src, "target": tgt, "note": note})

        if not terms_list:
            return ""

        lines = [
            f"### [2. TỪ ĐIỂN THUẬT NGỮ BẮT BUỘC ÁP DỤNG ({len(terms_list)} THUẬT NGỮ)]:",
            "Khi gặp các từ gốc tiếng Trung sau đây, BẮT BUỘC phải dịch chính xác thành từ tương ứng, KHÔNG ĐƯỢC tự ý dịch khác:"
        ]
        for t in terms_list:
            note_str = f" (Ngữ cảnh: {t['note']})" if t['note'] else ""
            lines.append(f"- \"{t['source']}\" ➔ DỊCH BẮT BUỘC THÀNH: \"{t['target']}\"{note_str}")

        return "\n".join(lines)

    @staticmethod
    def get_semantic_nuance_rules() -> str:
        return """
### QUY TẮC BẢO TOÀN NGỮ NGHĨA CHUYÊN SÂU & VĂN PHONG ĐIỆN ẢNH (CHÍNH XÁC TỪNG SẮC THÁI):
1. BẢO TOÀN SẮC THÁI CẢM XÚC & KHẨU KHÍ NHÂN VẬT (EMOTIONAL & REGISTER AWARENESS):
   - Tuyệt đối không dịch phẳng lì vô cảm! Hãy thấu hiểu cảm xúc nhân vật:
     * Cảnh chiến đấu / phẫn nộ / kịch tính: Dùng câu từ đanh thép, dứt khoát, giàu năng lượng (VD: "Chết tiệt!", "Cút ngay!", "Ngươi dám...!", "Đứng lại đó!").
     * Cảnh hài hước / trêu đùa: Dùng ngôn từ dí dỏm, khẩu ngữ tự nhiên đời thường (VD: "Có mà nằm mơ!", "Đùa chút thôi mà!", "Ảo thật đấy!").
     * Cảnh tâm trạng / xúc động: Dùng từ lắng đọng, nhịp điệu chậm rãi, giàu chất thơ và tình cảm.
     * Cảnh giải thích chuyên môn / khoa học / chiến thuật: Dùng thuật ngữ chuẩn xác, mạch lạc, dứt khoát.

2. XỬ LÝ THÀNH NGỮ, TỤC NGỮ, TỪ LÓNG (IDIOMS & SLANG TRANSFORMATION):
   - TUYỆT ĐỐI KHÔNG DỊCH WORD-BY-WORD nghĩa đen của thành ngữ hay từ lóng!
   - Bắt buộc chuyển đổi sang thành ngữ / quán ngữ / khẩu ngữ tiếng Việt tương đương:
     * Tiếng Anh: "Piece of cake" -> "Dễ như ăn kẹo" / "Chuyện nhỏ"; "Under the weather" -> "Hơi mệt trong người"; "Bite the bullet" -> "Cắn răng chịu đựng".
     * Tiếng Trung: "拍马屁" -> "Nịnh bợ / Vuốt mông ngựa"; "吃醋" -> "Ghen tuông"; "咸鱼" -> "Cá ươn / Kẻ lười biếng buông xuôi"; "画蛇添足" -> "Vẽ rắn thêm chân / Rườm rà thừa thãi".
     * Tiếng Nhật/Hàn: Chuyển các câu chào hỏi, thán từ, quán ngữ xã giao sang sắc thái tự nhiên của người Việt ("Cố lên nhé", "Vất vả rồi", "Làm phiền bạn quá").

3. CẶP XƯNG HÔ ĐỐI XỨNG & TÍNH NHẤT QUÁN TOÀN BỘ PHIM:
   - Nếu A gọi B là "Huynh", B phải xưng là "Đệ" hoặc "Ta", gọi A là "Đại ca/Huynh".
   - Nếu A gọi B là "Sư phụ", B xưng "Vi sư/Thầy", gọi A là "Đồ nhi/Con".
   - Nếu A gọi B là "Anh", B xưng "Em".
   - Không được đổi ngôi lộn xộn giữa chừng (ví dụ câu trước xưng "tôi - bạn", câu sau lại "mày - tao" trừ khi nhân vật thực sự trở mặt đối đầu).

4. TÍNH TOÀN VẸN & CHÍNH XÁC CỦA DỮ LIỆU SỐ HỌC / THỜI GIAN:
   - Các con số, thời gian, tên vũ khí, cấp độ tu vi/chiến lực, địa danh phải được dịch hoặc chuyển đổi hoàn toàn chính xác, không làm tròn sai lệch.

5. TRÁNH BẪY DỊCH MÁY ("TRANSLATIONESE"):
   - Loại bỏ các từ thừa làm câu cứng nhắc: Tránh lạm dụng từ "bị/được" theo cấu trúc bị động phương Tây, tránh dịch "one of the..." thành "một trong những..." nếu có thể diễn đạt gọn gàng hơn.
"""

    @classmethod
    def build_translation_prompt(
        cls,
        source_lang: str,
        target_lang: str,
        cues_to_translate: List[Dict[str, Any]],
        speaker_profiles: Optional[Dict[str, Any]] = None,
        relationship_matrix: Optional[Dict[str, Any]] = None,
        glossary: Optional[Dict[str, str]] = None,
        previous_context: Optional[List[Dict[str, Any]]] = None,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate system prompt and user prompt for LLM."""
        
        # System Prompt
        system_prompt = f"""Bạn là một Chuyên Gia AI Dịch Thuật Phụ Đề Video Chuyên Nghiệp Đỉnh Cao sang Tiếng Việt.
Nhiệm vụ: Dịch danh sách phụ đề video từ ngôn ngữ [{source_lang.upper()}] sang [{target_lang.upper()}].

{cls.get_language_specific_rules(source_lang)}

{cls.get_semantic_nuance_rules()}

### QUY TẮC BẮT BUỘC ĐỐI VỚI ĐỊNH DẠNG PHỤ ĐỀ:
1. GIỚI HẠN VẬT LÝ DÒNG PHỤ ĐỀ:
   - Độ dài tối đa mỗi dòng: {settings.MAX_SUBTITLE_LINE_LENGTH} ký tự.
   - Tối đa {settings.MAX_SUBTITLE_LINES} dòng cho một câu phụ đề. Nếu câu dài, hãy ngắt dòng bằng ký tự '\\n' tại vị trí ngắt câu hoặc ngắt ý tự nhiên.
   - Tốc độ đọc khuyến nghị <= {settings.MAX_CPS} CPS (Characters Per Second). Hãy dịch súc tích, gãy gọn, tránh từ đệm rườm rà.
2. ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (JSON ONLY):
Trả về DUY NHẤT một JSON Object hợp lệ theo cấu trúc sau, không kèm bất kỳ giải thích nào khác:
{{
  "translations": [
    {{
      "id": 1,
      "text": "Câu dịch tiếng Việt đã được ngắt dòng hợp lý"
    }}
  ]
}}
"""

        # Build Context Components for User Prompt
        context_parts = []

        # 1. Speaker Profiles & Pronouns (Imperative Directives)
        speaker_rules = cls.format_speaker_and_relationship_rules(speaker_profiles, relationship_matrix)
        if speaker_rules:
            context_parts.append(speaker_rules)

        # 2. Glossary (Mandatory Directives)
        glossary_rules = cls.format_glossary_rules(glossary)
        if glossary_rules:
            context_parts.append(glossary_rules)

        # 3. Previous Context
        if previous_context and len(previous_context) > 0:
            context_parts.append(f"### [3. NGỮ CẢNH HỘI THOẠI VỪA DIỄN RA (5 CÂU TRƯỚC ĐÓ ĐỂ GIỮ MẠCH NỘI DUNG)]:\n{json.dumps(previous_context, ensure_ascii=False, indent=2)}")

        # 4. Custom Instructions if any
        if custom_instructions:
            context_parts.append(f"### [4. YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG]:\n{custom_instructions}")

        # 5. Target cues to translate
        context_parts.append(f"### [DANH SÁCH PHỤ ĐỀ CẦN DỊCH NGAY ({len(cues_to_translate)} CÂU)]:\n{json.dumps(cues_to_translate, ensure_ascii=False, indent=2)}")

        user_prompt = "\n\n".join(context_parts)

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }

    @staticmethod
    def build_reflexion_prompt(
        violation_report: List[Dict[str, Any]],
        speaker_profiles: Optional[Dict[str, Any]] = None,
        relationship_matrix: Optional[Dict[str, Any]] = None,
        glossary: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Builds a targeted fast-fix reflexion prompt to correct only violated subtitle lines."""
        system_prompt = """Bạn là Guardrail Fast-Fixer chuyên sửa lỗi định dạng, đại từ xưng hô và giới hạn phụ đề.
Nhiệm vụ: Viết lại DUY NHẤT các câu phụ đề bị vi phạm để thỏa mãn 100% các tiêu chí chất lượng.

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (JSON ONLY):
{
  "translations": [
    {
      "id": 12,
      "text": "Câu dịch đã được sửa ngắn gọn và xưng hô chuẩn xác"
    }
  ]
}
"""
        user_prompt = f"""Các câu phụ đề sau đây đã vi phạm tiêu chuẩn chất lượng:
{json.dumps(violation_report, ensure_ascii=False, indent=2)}

Quy tắc hồ sơ nhân vật: {json.dumps(relationship_matrix or {}, ensure_ascii=False)}
Quy tắc từ điển: {json.dumps(glossary or {}, ensure_ascii=False)}

Hãy viết lại các câu trên sao cho:
1. Độ dài mỗi dòng <= {settings.MAX_SUBTITLE_LINE_LENGTH} ký tự (dùng '\\n' để ngắt dòng nếu cần, tối đa 2 dòng).
2. Xưng hô đúng tuyệt đối theo ma trận.
3. Thuật ngữ đúng theo Glossary.
4. Trả về đúng ID của các câu vi phạm.
"""
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
