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
### QUY TẮC DỊCH TIẾNG ANH CHUYÊN SÂU (ENGLISH -> VIETNAMESE):
1. ĐẠI TỪ XƯNG HÔ ĐỐI THOẠI:
   - Tuyệt đối KHÔNG dịch cứng nhắc I/You thành "Tôi/Bạn". Phải căn cứ vào BẢNG HỒ SƠ NHÂN VẬT & QUY TẮC XƯNG HÔ để dịch thành cặp xưng hô tiếng Việt tự nhiên (Anh/Em, Chú/Cháu, Sếp/Em, Bố/Con, Cậu/Mình, Mày/Tao...).
   - Khử đại từ trung tính (We, They) thành "chúng tôi", "chúng ta", "tụi mình", "bọn họ", "bọn chúng" phù hợp với sắc thái cảnh phim.
2. PHRASAL VERBS, IDIOMS & SLANG (THOÁT NGHĨA ĐIỆN ẢNH):
   - Dịch thoát ý theo thành ngữ/quán ngữ tiếng Việt tự nhiên, TUYỆT ĐỐI KHÔNG dịch từng chữ (word-by-word):
     * "break a leg" -> "chúc may mắn nhé" / "diễn tốt nhé".
     * "bite the bullet" -> "cắn răng chịu đựng" / "đành phải chấp nhận thôi".
     * "hit the nail on the head" -> "nói chuẩn không cần chỉnh" / "đúng trọng tâm rồi".
     * "out of the blue" -> "bất thình lình" / "tự nhiên từ trên trời rơi xuống".
     * "under the weather" -> "hơi mệt trong người" / "thấy khó ở".
     * "piece of cake" -> "dễ như ăn kẹo" / "chuyện nhỏ như con thỏ".
     * "call it a day" -> "nghỉ tay thôi" / "hôm nay thế là đủ rồi".
     * "cost an arm and a leg" -> "đắt cắt cổ" / "tốn cả gia tài".
3. THUẬT NGỮ CHUYÊN NGÀNH & BẢN ĐỊA HÓA CÔNG NGHỆ / TÀI CHÍNH:
   - Giữ nguyên các từ kỹ thuật/công nghệ quốc tế quen thuộc (VD: API, Backend, Frontend, Microservices, Database, Cache, CI/CD).
   - Dịch chuẩn các thuật ngữ kinh doanh/pháp lý (VD: ROI -> tỷ suất hoàn vốn, Due Diligence -> thẩm định chuyên sâu, Search Warrant -> lệnh khám xét).
4. KHẮC PHỤC THỂ BỊ ĐỘNG CỨNG NHẮC ("TRANSLATIONESE"):
   - Chuyển câu bị động tiếng Anh sang câu chủ động tiếng Việt (VD: "The code was written by him" -> "Chính anh ấy đã viết đoạn mã đó", tránh dùng "Mã đã bị viết bởi anh ấy").
"""
        elif lang in ["zh", "chinese", "zh-cn", "zh-tw"]:
            return """
### QUY TẮC ĐẶC BIỆT BẮT BUỘC KHI DỊCH TIẾNG TRUNG (CHINESE -> VIETNAMESE):
1. ĐẶC BIỆT CHÚ Ý GIỚI TÍNH & ĐẠI TỪ XƯNG HÔ (CỰC KỲ QUAN TRỌNG):
   - Trong tiếng Trung khẩu ngữ và nhận diện ASR, từ "tā" thường bị viết thành "他" (nam) dù nhân vật trong phim là NỮ ("她")!
   - BẮT BUỘC PHÂN TÍCH KỸ NGỮ CẢNH HỘI THOẠI & BẢNG HỒ SƠ NHÂN VẬT:
     * Khi nhân vật NỮ nói hoặc đối tượng được nhắc đến là NỮ (như Cố Vãn Chu - 顾晚舟, cô bé, bạn gái, cô gái, nữ sinh):
       TUYỆT ĐỐI KHÔNG dịch thành "anh ta", "anh ấy", "hắn"!
       PHẢI dịch là: "cô ấy", "em ấy", "cô ta", "cô", "em", "nàng".
     * Khi nhân vật NAM (như Mục Thần - 牧尘, nam sinh, thiếu niên): Dùng "cậu ấy", "anh ấy", "hắn", "cậu".
     * Xưng hô đối thoại nam - nữ đồng trang lứa: "tôi - cô", "cậu - tôi", "anh - em" tự nhiên.
     * Xưng hô với giáo viên (Thầy Lâm / 林老师): "Thầy - em / con".
     * Đối với kẻ địch / phản diện (Bạch Cốt Lâu / 白骨楼): "bọn chúng", "ngươi - ta", "mày - tao".

2. PHỤC HỒI TỪ ĐỒNG ÂM ASR & DỊCH SÁT BỐI CẢNH MECHA SCI-FI / KHOA HỌC VIỄN TƯỞNG:
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
     * 白骨楼 (hoặc ASR nhận nhầm 白酷楼) -> "Bạch Cốt Lâu" (tổ chức phản diện).
     * 顾晚舟 -> "Cố Vãn Chu" (nhân vật NỮ).
     * 牧尘 -> "Mục Thần" (nhân vật NAM chính).
     * 林老师 -> "Thầy Lâm".
     * 战舰 -> "Chiến hạm", 虫族 -> "Trùng tộc", 离子炮 -> "Pháo ion".

3. QUY TẮC HÁN-VIỆT VS THUẦN-VIỆT THEO THỂ LOẠI PHIM:
   - Phim Cổ trang, Kiếm hiệp, Tu tiên: Dùng âm Hán-Việt uy nghiêm (Sư tôn, Đồ nhi, Chưởng môn, Đan điền, Bế quan, Độ kiếp, Bệ hạ, Vi thần).
   - Phim Hiện đại, Đô thị, Đời sống: BẮT BUỘC dùng từ Thuần-Việt tự nhiên (Ăn cơm, Tiện lợi, Ghen tuông, Bạn thân, Cố lên).

4. CHUYỂN HÓA THÀNH NGỮ 4 CHỮ & TỪ LÓNG HIỆN ĐẠI:
   - "吃醋" -> "ghen tuông"; "拍马屁" -> "nịnh bợ"; "咸鱼" -> "cá ươn / kẻ buông xuôi"; "躺平" -> "nằm yên buông xuôi"; "破防" -> "suy sụp / vỡ òa"; "吐槽" -> "cà khịa / bóc phốt".
"""
        elif lang in ["ja", "japanese"]:
            return """
### QUY TẮC DỊCH TIẾNG NHẬT CHUYÊN SÂU (JAPANESE -> VIETNAMESE):
1. KÍNH NGỮ KEIGO THEO CẤP BẬC XÃ HỘI:
   - Sonkeigo (Tôn kính ngữ) & Kenjougo (Khiêm nhường ngữ):
     * Dịch kèm sắc thái trang trọng, thêm kính từ "dạ / thưa / vâng / kính xin" phù hợp vị thế.
     * "承知いたしました" -> "tôi đã rõ rồi ạ" / "xin ghi nhận ạ".
     * "よろしくお願いいたします" -> "trăm sự nhờ anh/chị ạ" / "rất mong được giúp đỡ ạ".
     * "お疲れ様でした" -> "anh/chị đã vất vả rồi ạ".
   - Tameguchi (Thân mật bạn bè / gia đình): Dịch gần gũi, thoải mái, tự nhiên.
2. HẬU TỐ DANH XƯNG & QUAN HỆ NHÂN VẬT:
   - '-san' -> Anh / Chị / Bạn [Tên].
   - '-sama' -> Ngài / Quý khách / Tiểu thư [Tên].
   - '-sensei' -> Thầy / Cô / Bác sĩ [Tên].
   - '-senpai' -> Tiền bối / Anh / Chị [Tên].
   - '-kohai' -> Hậu bối / Em khóa dưới.
   - '-chan / -kun' -> Bé / Em / Cậu [Tên].
   - 'Aniki' -> Đại ca / Anh hai.
3. ĐẠI TỪ TỰ XƯNG & KHẨU KHÍ NHÂN VẬT:
   - Watashi/Watakushi -> Tôi / Em / Con.
   - Boku/Ore -> Tôi / Cậu / Tao / Anh / Mình (tùy độ thân mật và tình huống).
   - Anata/Omae/Kimi -> Bạn / Cậu / Mày / Em.
4. TỪ CẢM THÁN & ĐỐI THOẠI ANIME / ĐIỆN ẢNH:
   - "まさか" -> "không lẽ nào..." / "chẳng lẽ..."; "嘘でしょ" -> "đùa nhau chắc!" / "không thể nào!"; "やれやれ" -> "thật là bó tay luôn".
"""
        elif lang in ["ko", "korean"]:
            return """
### QUY TẮC DỊCH TIẾNG HÀN CHUYÊN SÂU (KOREAN -> VIETNAMESE):
1. KÍNH NGỮ (JONDAETMAL) vs THÂN MẬT (BANMAL):
   - Đuôi câu kính ngữ '-습니다 / -십니까 / -해요': Bắt buộc thể hiện sự lễ phép, thêm "dạ / thưa / vâng / ạ".
     * "알겠습니다" -> "tôi hiểu rồi ạ" / "tôi rõ rồi ạ".
     * "죄송합니다" -> "tôi vô cùng xin lỗi ạ".
   - Đuôi câu thân mật '-야 / -어 / -지': Xưng hô thoải mái, dùng đại từ thân thiết hoặc mày/tao tùy ngữ cảnh.
2. DANH XƯNG XÃ HỘI & GIA ĐÌNH:
   - Oppa (오빠) -> Anh (nữ gọi bạn trai hoặc anh trai thân thiết).
   - Hyung (형) -> Anh (nam gọi anh trai hoặc bạn nam lớn tuổi).
   - Noona (누나) / Unnie (언니) -> Chị.
   - Sunbae-nim (선배님) -> Tiền bối / Anh/Chị.
   - Hoobae (후배) -> Hậu bối / Em khóa dưới.
   - Daepyo-nim (대표님) -> Giám đốc / Sếp.
   - Teamjang-nim (팀장님) -> Trưởng nhóm / Trưởng phòng.
   - Ajusshi (아저씨) -> Chú / Bác; Ajumma (아줌마) -> Cô / Bác gái.
3. TỪ LÓNG DRAMA & CẢM THÁN GIỚI TRẺ:
   - "대박" -> "đỉnh chóp luôn" / "tuyệt vời thật"; "화이팅" -> "cố lên nào!"; "헐" -> "trời đất ơi"; "진짜" -> "thật sao?".
   - Chaebol -> Tài phiệt; Gapjil -> Thói lộng quyền; Cider -> Hả dạ cực kỳ; Goguma -> Ức chế nghẹn họng.
"""
        else:
            return """
### NGUYÊN TẮC DỊCH CHUNG:
- Văn phong tự nhiên, thuần Việt, đúng ngữ cảnh đối thoại thực tế.
- Tuân thủ bảng hồ sơ nhân vật và quan hệ xưng hô.
"""

    @staticmethod
    def get_video_grounded_translation_rules() -> str:
        return """
### NGUYÊN TẮC DỊCH THUẬT DỰA TRÊN NGỮ CẢNH THỊ GIÁC VIDEO (VIDEO-GROUNDED TRANSLATION):
Khi dịch phụ đề video, văn bản thoại PHẢI hòa quyện tuyệt đối với hình ảnh và diễn biến trên màn hình:
1. GIẢI MÃ TÍN HIỆU THỊ GIÁC & CẢM XÚC NHÂN VẬT (FACIAL & EMOTIONAL GROUNDING):
   - Quan sát biểu cảm gương mặt và khẩu hình:
     * Cười nhếch mép, mỉa mai, trêu ghẹo: Dùng các trợ từ khẩu ngữ tiếng Việt tự nhiên (*cơ đấy, cơ à, đấy nhé, chứ ai, hả*).
     * Mắt ngấn lệ, nghẹn ngào, thì thầm: Dùng từ ngữ lắng đọng, dịu dàng, tránh dùng từ thô ráp cứng nhắc (*anh xin lỗi, em đừng khóc nữa mà*).
     * Nhe răng gầm thét, mắt long lên sòng sọc, cầm vũ khí: Dùng khẩu khí đanh thép, bộc trực (*chết tiệt, cút ngay, đồ khốn, tao sẽ tiêu diệt mày*).
     * Cúi gập người, hai tay đan chéo cung kính: Dùng kính ngữ lễ phép (*dạ, thưa anh, xin sếp yên tâm ạ*).

2. KHOẢNG CÁCH KHÔNG GIAN & VỊ THẾ XÃ HỘI (PROXEMICS & HIERARCHY):
   - Cảnh cận cảnh / hai người ôm nhau hoặc đứng sát nhau: Không dùng đại từ xa cách "tôi - cô", mà dùng "anh - em", "mình - cậu".
   - Cảnh phòng họp lớn / đứng trước bàn làm việc của cấp trên: Giữ vững tôn ti công sở "sếp - em", "giám đốc - tôi".
   - Cảnh chiến trường / hai bên đứng đối mặt rút gươm/súng: Dùng cặp xưng hô đối đầu ("ngươi - ta", "mày - tao", "bọn mày - bọn tao").

3. ĐỒNG BỘ HÀNH ĐỘNG THỰC TẾ & KHỬ TỪ ĐA NGHĨA (MULTIMODAL DISAMBIGUATION):
   - Từ đa nghĩa tiếng Anh/Trung/Nhật/Hàn BẮT BUỘC phải đối chiếu với vật thể nhân vật đang tương tác:
     * "Fire!": Nếu nhân vật cầm súng hoặc pháo đài -> Dịch là "Bắn!" / "Khai hỏa!", TUYỆT ĐỐI KHÔNG dịch "Lửa!".
     * "Bank": Nếu nhân vật đứng bên bờ suối -> Dịch "bờ sông/bờ suối"; nếu đứng trước tòa nhà tài chính -> Dịch "ngân hàng".
     * "Strike": Cảnh máy bay bay qua thả bom -> Dịch "không kích"; cảnh công nhân giơ băng rôn -> Dịch "đình công"; cảnh thi đấu võ/bowling -> Dịch "tung đòn / ghi điểm tuyệt đối".
     * Tiếng Trung "打" (dǎ): Cầm gậy/nắm đấm -> "Đánh!"; cầm điện thoại -> "Gọi điện"; cầm vé -> "Mua vé/Bấm vé"; gõ bàn phím -> "Gõ/Nhập dữ liệu".

4. ĐỒNG BỘ NHỊP ĐIỆU PHỤ ĐỀ VỚI NHỊP CẮT DỰNG CỦA PHIM (PACING & READING COMFORT):
   - Cảnh hành động chớp nhoáng (Fast-paced scene, nhiều jump cut): Dịch câu ngắn gọn, dứt khoát, không dùng từ đệm rườm rà để khán giả kịp đọc dưới 18 CPS.
   - Cảnh sâu lắng, tự sự dài (Slow-paced, long take): Dịch uyển chuyển, giàu tính văn học và âm điệu tiếng Việt.
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
        custom_instructions: Optional[str] = None,
        video_context: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate system prompt and user prompt for LLM."""
        
        # System Prompt
        system_prompt = f"""Bạn là một Chuyên Gia AI Dịch Thuật Phụ Đề Video Chuyên Nghiệp Đỉnh Cao sang Tiếng Việt.
Nhiệm vụ: Dịch danh sách phụ đề video từ ngôn ngữ [{source_lang.upper()}] sang [{target_lang.upper()}].

{cls.get_language_specific_rules(source_lang)}

{cls.get_video_grounded_translation_rules()}

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

        # 1. Video Visual Context if available
        if video_context:
            context_parts.append(f"### [BỐI CẢNH & TÍN HIỆU THỊ GIÁC VIDEO (VIDEO VISUAL CONTEXT)]:\n{video_context}")

        # 2. Speaker Profiles & Pronouns (Imperative Directives)
        speaker_rules = cls.format_speaker_and_relationship_rules(speaker_profiles, relationship_matrix)
        if speaker_rules:
            context_parts.append(speaker_rules)

        # 3. Glossary (Mandatory Directives)
        glossary_rules = cls.format_glossary_rules(glossary)
        if glossary_rules:
            context_parts.append(glossary_rules)

        # 4. Previous Context
        if previous_context and len(previous_context) > 0:
            context_parts.append(f"### [4. NGỮ CẢNH HỘI THOẠI VỪA DIỄN RA (5 CÂU TRƯỚC ĐÓ ĐỂ GIỮ MẠCH NỘI DUNG)]:\n{json.dumps(previous_context, ensure_ascii=False, indent=2)}")

        # 5. Custom Instructions if any
        if custom_instructions:
            context_parts.append(f"### [5. YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG]:\n{custom_instructions}")

        # 6. Target cues to translate
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
