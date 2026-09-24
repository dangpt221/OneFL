"""Curated Genre Presets for Film & Series Translation Studio.
Allows 1-click loading of terminology and speaker configurations across movies.
"""

from typing import Dict, Any, List

GENRE_PRESETS: Dict[str, Dict[str, Any]] = {
    "sci_fi_mecha": {
        "id": "sci_fi_mecha",
        "name": "Khoa Huyễn & Cơ Giáp Không Gian",
        "icon": "🚀",
        "genre": "Khoa Huyễn / Mecha",
        "description": "Thư viện chuẩn điện ảnh cho phim hoạt hình 3D, anime chiến hạm, robot cơ giáp, tinh cầu, trí tuệ nhân tạo và hành tinh phế liệu.",
        "speakers": [
            {
                "speaker_tag": "SPEAKER_00",
                "display_name": "Mục Thần",
                "original_name": "牧尘 (Mù Chén)",
                "aliases": "Mục ca, Tiểu Thần",
                "avatar_color": "#6366f1",
                "gender": "male",
                "age_group": "young_adult",
                "role": "Nam chính - Thiên tài cơ giáp",
                "tone": "Điềm đạm, quyết đoán, tự tin",
                "tts_voice": "vi-VN-HoaiMyNeural",
                "tts_speed": 1.0,
                "notes": "Nhân vật nam chính. Xưng 'Tôi' hoặc 'Cậu' với bạn bè, xưng 'Em' với thầy."
            },
            {
                "speaker_tag": "SPEAKER_01",
                "display_name": "Cố Vãn Chu",
                "original_name": "顾晚舟 (Gù Wǎnzhōu)",
                "aliases": "Vãn Chu, Chu muội",
                "avatar_color": "#ec4899",
                "gender": "female",
                "age_group": "young_adult",
                "role": "Nữ chính - Thiên kim tiểu thư",
                "tone": "Trong trẻo, thông minh, dũng cảm",
                "tts_voice": "vi-VN-HoaiMyNeural",
                "tts_speed": 1.0,
                "notes": "Nhân vật NỮ chính. TUYỆT ĐỐI KHÔNG dịch là anh ta hay hắn. Dịch: cô ấy, em ấy, nàng."
            },
            {
                "speaker_tag": "SPEAKER_02",
                "display_name": "Trợ Lý AI",
                "original_name": "智能系统 (AI Assistant)",
                "aliases": "Hệ thống, Trí năng",
                "avatar_color": "#06b6d4",
                "gender": "neutral",
                "age_group": "immortal",
                "role": "Trí tuệ nhân tạo chiến hạm",
                "tone": "Khách quan, chính xác, máy móc",
                "tts_voice": "alloy",
                "tts_speed": 1.0,
                "notes": "Báo cáo trạng thái, cảnh báo nguy hiểm. Xưng 'Hệ thống' hoặc 'Tôi'."
            },
            {
                "speaker_tag": "SPEAKER_03",
                "display_name": "Thầy Lâm",
                "original_name": "林老师 (Teacher Lin)",
                "aliases": "Lâm đạo sư",
                "avatar_color": "#10b981",
                "gender": "male",
                "age_group": "adult",
                "role": "Giáo viên hướng dẫn cơ giáp",
                "tone": "Uy nghiêm, ân cần, từng trải",
                "tts_voice": "vi-VN-NamMinhNeural",
                "tts_speed": 1.0,
                "notes": "Người chỉ dẫn thế hệ trẻ. Xưng 'Thầy' với học trò."
            }
        ],
        "relationships": [
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_01",
                "self_pronoun": "Tôi",
                "target_pronoun": "Cô / Em",
                "relationship_type": "Bạn đồng hành",
                "honorific_notes": "Quan hệ tự nhiên, thân thiết dần theo thời gian."
            },
            {
                "source_speaker": "SPEAKER_01",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Tôi / Em",
                "target_pronoun": "Cậu / Anh",
                "relationship_type": "Bạn đồng hành",
                "honorific_notes": "Gọi nam chính là cậu hoặc anh."
            },
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_03",
                "self_pronoun": "Em / Con",
                "target_pronoun": "Thầy",
                "relationship_type": "Thầy - Trò",
                "honorific_notes": "Kính trọng thầy giáo."
            },
            {
                "source_speaker": "SPEAKER_03",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Thầy",
                "target_pronoun": "Em / Cậu",
                "relationship_type": "Thầy - Trò",
                "honorific_notes": "Thầy nói chuyện với học trò."
            }
        ],
        "terms": [
            {"source_term": "垃圾星", "target_term": "Tinh cầu rác", "category": "LOCATION", "context_note": "Hành tinh phế liệu bãi rác vũ trụ (cấm dịch máy kéo)"},
            {"source_term": "星际学院", "target_term": "Học viện Tinh tế", "category": "LOCATION", "context_note": "Học viện đào tạo phi công cơ giáp"},
            {"source_term": "机甲", "target_term": "Cơ giáp", "category": "WEAPON_MECHA", "context_note": "Người máy chiến đấu mecha bọc thép"},
            {"source_term": "超神机甲", "target_term": "Cơ giáp Siêu Thần", "category": "WEAPON_MECHA", "context_note": "Cơ giáp cấp thần đỉnh cao vũ trụ"},
            {"source_term": "飞行器", "target_term": "Phi hành khí", "category": "WEAPON_MECHA", "context_note": "Tàu bay mini, phi thuyền cá nhân"},
            {"source_term": "反物质粒子炮", "target_term": "Pháo Hạt Phản Vật Chất", "category": "WEAPON_MECHA", "context_note": "Vũ khí hủy diệt năng lượng cao"},
            {"source_term": "等离子光刃", "target_term": "Đao Plasma", "category": "WEAPON_MECHA", "context_note": "Vũ khí cận chiến của cơ giáp"},
            {"source_term": "能量护盾", "target_term": "Khiên Năng Lượng", "category": "WEAPON_MECHA", "context_note": "Lớp bảo hộ trường lực"},
            {"source_term": "圣金", "target_term": "Thánh Kim", "category": "WEAPON_MECHA", "context_note": "Kim loại vũ trụ cực hiếm chế tạo lõi cơ giáp"},
            {"source_term": "源晶", "target_term": "Nguyên Tinh", "category": "WEAPON_MECHA", "context_note": "Khối tinh thể năng lượng nguồn"},
            {"source_term": "精神力", "target_term": "Tinh thần lực", "category": "RANK_REALM", "context_note": "Chỉ số sóng não điều khiển cơ giáp"},
            {"source_term": "神经同步率", "target_term": "Độ đồng bộ nơ-ron", "category": "RANK_REALM", "context_note": "Mức độ hòa hợp giữa người lái và cơ giáp"},
            {"source_term": "觉醒者", "target_term": "Người Giác Tỉnh", "category": "RANK_REALM", "context_note": "Người sở hữu siêu năng lực tinh thần"},
            {"source_term": "白骨楼", "target_term": "Bạch Cốt Lâu", "category": "ORGANIZATION", "context_note": "Tổ chức sát thủ phản diện nguy hiểm"},
            {"source_term": "白酷楼", "target_term": "Bạch Cốt Lâu", "category": "ORGANIZATION", "context_note": "ASR nhận diện nhầm âm của Bạch Cốt Lâu"},
            {"source_term": "捡垃圾", "target_term": "Nhặt phế liệu", "category": "SLANG_IDIOM", "context_note": "Thu gom ve chai linh kiện cơ giáp phế thải"},
            {"source_term": "曲速跃迁", "target_term": "Bước nhảy Warp", "category": "SLANG_IDIOM", "context_note": "Nhảy vọt không gian vận tốc ánh sáng"},
            {"source_term": "AI", "target_term": "AI", "category": "DO_NOT_TRANSLATE", "context_note": "Trí tuệ nhân tạo, giữ nguyên"},
            {"source_term": "HUD", "target_term": "HUD", "category": "DO_NOT_TRANSLATE", "context_note": "Giao diện hiển thị kính lái"}
        ]
    },
    "xianxia_cultivation": {
        "id": "xianxia_cultivation",
        "name": "Tiên Hiệp & Tu Chân Huyền Huyễn",
        "icon": "⚔️",
        "genre": "Tiên Hiệp / Tu Chân",
        "description": "Kho thuật ngữ và danh xưng kinh điển cho phim tiên hiệp, huyền huyễn, cảnh giới tu vi, đan dược, tông môn và pháp bảo.",
        "speakers": [
            {
                "speaker_tag": "SPEAKER_00",
                "display_name": "Nam Chính Tu Chân",
                "original_name": "主角 (Main Protagonist)",
                "aliases": "Tiểu hữu, Sư đệ",
                "avatar_color": "#8b5cf6",
                "gender": "male",
                "age_group": "young_adult",
                "role": "Thiếu niên quật khởi",
                "tone": "Kiên cường, cơ trí, điềm tĩnh",
                "tts_voice": "vi-VN-NamMinhNeural",
                "tts_speed": 1.0,
                "notes": "Tu sĩ nghịch thiên cải mệnh. Xưng 'Tại hạ / Đệ tử / Ta'."
            },
            {
                "speaker_tag": "SPEAKER_01",
                "display_name": "Sư Phụ / Chưởng Môn",
                "original_name": "师尊 (Master)",
                "aliases": "Vi sư, Chưởng môn",
                "avatar_color": "#d97706",
                "gender": "male",
                "age_group": "senior",
                "role": "Tiên nhân đắc đạo",
                "tone": "Uy nghiêm, từ ái, cao thâm",
                "tts_voice": "vi-VN-NamMinhNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Vi sư' hoặc 'Bản tọa' khi nói với đồ đệ."
            },
            {
                "speaker_tag": "SPEAKER_02",
                "display_name": "Tiểu Sư Muội",
                "original_name": "小师妹 (Junior Sister)",
                "aliases": "Sư muội",
                "avatar_color": "#f43f5e",
                "gender": "female",
                "age_group": "teen",
                "role": "Đồng môn ngây thơ",
                "tone": "Lanh lợi, hoạt bát, quan tâm",
                "tts_voice": "vi-VN-HoaiMyNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Muội / Em', gọi 'Sư huynh / Huynh'."
            }
        ],
        "relationships": [
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_01",
                "self_pronoun": "Đồ nhi / Con",
                "target_pronoun": "Sư phụ / Tôn sư",
                "relationship_type": "Sư đồ",
                "honorific_notes": "Kính trọng sư phụ tôn nghiêm."
            },
            {
                "source_speaker": "SPEAKER_01",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Vi sư",
                "target_pronoun": "Đồ nhi / Con",
                "relationship_type": "Sư đồ",
                "honorific_notes": "Sư phụ dạy bảo đồ đệ."
            },
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_02",
                "self_pronoun": "Huynh",
                "target_pronoun": "Sư muội / Muội",
                "relationship_type": "Đồng môn",
                "honorific_notes": "Sư huynh bảo bọc sư muội."
            },
            {
                "source_speaker": "SPEAKER_02",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Muội",
                "target_pronoun": "Sư huynh",
                "relationship_type": "Đồng môn",
                "honorific_notes": "Sư muội tôn sùng sư huynh."
            }
        ],
        "terms": [
            {"source_term": "练气期", "target_term": "Luyện Khí Kỳ", "category": "RANK_REALM", "context_note": "Cảnh giới sơ khai của người tu tiên"},
            {"source_term": "筑基期", "target_term": "Trúc Cơ Kỳ", "category": "RANK_REALM", "context_note": "Cảnh giới đặt nền móng tu đạo"},
            {"source_term": "金丹期", "target_term": "Kim Đan Kỳ", "category": "RANK_REALM", "context_note": "Cảnh giới kết đan trong đan điền"},
            {"source_term": "元婴期", "target_term": "Nguyên Anh Kỳ", "category": "RANK_REALM", "context_note": "Cảnh giới hóa sinh nguyên anh bất tử"},
            {"source_term": "化神期", "target_term": "Hóa Thần Kỳ", "category": "RANK_REALM", "context_note": "Cảnh giới câu thông thiên địa đại đạo"},
            {"source_term": "渡劫", "target_term": "Độ Kiếp", "category": "RANK_REALM", "context_note": "Vượt qua thiên lôi giáng thế để phi thăng"},
            {"source_term": "神识", "target_term": "Thần thức", "category": "RANK_REALM", "context_note": "Giác quan linh hồn dò xét vạn vật"},
            {"source_term": "丹田", "target_term": "Đan điền", "category": "RANK_REALM", "context_note": "Nơi tích tụ chân khí linh lực"},
            {"source_term": "本命法宝", "target_term": "Pháp bảo bản mệnh", "category": "WEAPON_MECHA", "context_note": "Vũ khí liên kết linh hồn với tu sĩ"},
            {"source_term": "飞剑", "target_term": "Phi kiếm", "category": "WEAPON_MECHA", "context_note": "Kiếm ngự không bay lượn"},
            {"source_term": "极品灵石", "target_term": "Linh thạch cực phẩm", "category": "WEAPON_MECHA", "context_note": "Đá chứa linh khí thuần khiết nhất"},
            {"source_term": "宗门", "target_term": "Tông môn", "category": "ORGANIZATION", "context_note": "Môn phái tu tiên"},
            {"source_term": "魔道", "target_term": "Ma đạo", "category": "ORGANIZATION", "context_note": "Phe phái tà ma phản diện"},
            {"source_term": "远古秘境", "target_term": "Bí cảnh Viễn cổ", "category": "LOCATION", "context_note": "Vùng đất cấm địa chứa cơ duyên ngàn năm"},
            {"source_term": "逆天改命", "target_term": "Nghịch thiên cải mệnh", "category": "SLANG_IDIOM", "context_note": "Chống lại số trời định đoạt số phận"},
            {"source_term": "杀人夺宝", "target_term": "Giết người đoạt bảo", "category": "SLANG_IDIOM", "context_note": "Hành vi cướp bóc tàn độc của tu tiên giới"}
        ]
    },
    "wuxia_ancient": {
        "id": "wuxia_ancient",
        "name": "Kiếm Hiệp & Cổ Trang Giang Hồ",
        "icon": "🗡️",
        "genre": "Kiếm Hiệp / Cổ Trang",
        "description": "Thuật ngữ giang hồ võ lâm, môn phái chính tà, tuyệt học võ công, huynh đệ kết nghĩa và xưng hô cổ trang chuẩn vị.",
        "speakers": [
            {
                "speaker_tag": "SPEAKER_00",
                "display_name": "Đại Hiệp",
                "original_name": "大侠 (Hero)",
                "aliases": "Đại ca, Huynh đài",
                "avatar_color": "#2563eb",
                "gender": "male",
                "age_group": "adult",
                "role": "Hiệp khách giang hồ",
                "tone": "Hào sảng, trọng nghĩa khí, bộc trực",
                "tts_voice": "vi-VN-NamMinhNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Tại hạ / Ta / Huynh', gọi 'Các hạ / Hiền đệ'."
            },
            {
                "speaker_tag": "SPEAKER_01",
                "display_name": "Chưởng Môn",
                "original_name": "掌门 (Sect Leader)",
                "aliases": "Minh chủ",
                "avatar_color": "#475569",
                "gender": "male",
                "age_group": "senior",
                "role": "Người đứng đầu danh môn chính phái",
                "tone": "Trang nghiêm, thâm trầm, mẫu mực",
                "tts_voice": "onyx",
                "tts_speed": 1.0,
                "notes": "Xưng 'Bản toạ / Lão phu'."
            }
        ],
        "relationships": [
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_01",
                "self_pronoun": "Vãn bối / Tại hạ",
                "target_pronoun": "Tiền bối / Chưởng môn",
                "relationship_type": "Tiền bối - Hậu bối",
                "honorific_notes": "Lễ nghi giang hồ kính trọng tiền nhân."
            },
            {
                "source_speaker": "SPEAKER_01",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Lão phu / Ta",
                "target_pronoun": "Thiếu hiệp / Ngươi",
                "relationship_type": "Tiền bối - Hậu bối",
                "honorific_notes": "Bậc tiền bối nói chuyện với thiếu hiệp."
            }
        ],
        "terms": [
            {"source_term": "江湖", "target_term": "Giang hồ", "category": "LOCATION", "context_note": "Thế giới võ lâm đầy hiểm nguy"},
            {"source_term": "武林盟主", "target_term": "Minh chủ Võ lâm", "category": "ORGANIZATION", "context_note": "Người đứng đầu toàn bộ võ lâm chính đạo"},
            {"source_term": "镖局", "target_term": "Tiêu cục", "category": "ORGANIZATION", "context_note": "Đơn vị vận chuyển hàng hóa bảo an cổ đại"},
            {"source_term": "内力", "target_term": "Nội lực", "category": "RANK_REALM", "context_note": "Sức mạnh khí công trong cơ thể"},
            {"source_term": "真气", "target_term": "Chân khí", "category": "RANK_REALM", "context_note": "Khí tức luyện tập võ học cao thâm"},
            {"source_term": "秘籍", "target_term": "Bí kíp võ công", "category": "WEAPON_MECHA", "context_note": "Sách ghi chép tuyệt học trấn phái"},
            {"source_term": "点穴", "target_term": "Điểm huyệt", "category": "RANK_REALM", "context_note": "Kỹ pháp khống chế kinh mạch đối phương"},
            {"source_term": "结拜兄弟", "target_term": "Huynh đệ kết nghĩa", "category": "SLANG_IDIOM", "context_note": "Anh em thề kết nghĩa sống chết có nhau"},
            {"source_term": "恩怨情仇", "target_term": "Ân oán tình thù", "category": "SLANG_IDIOM", "context_note": "Mối thù oán và ân nghĩa đan xen"}
        ]
    },
    "anime_manga": {
        "id": "anime_manga",
        "name": "Anime, Manga & Dị Giới Isekai",
        "icon": "⛩️",
        "genre": "Anime / Isekai",
        "description": "Thư viện chuyên dụng cho hoạt hình Nhật Bản, du hành dị giới (isekai), ma pháp học viện, dũng giả, ma vương và xưng hô kính ngữ.",
        "speakers": [
            {
                "speaker_tag": "SPEAKER_00",
                "display_name": "Nam Chính Dũng Giả",
                "original_name": "勇者 (Hero)",
                "aliases": "Dũng giả",
                "avatar_color": "#0284c7",
                "gender": "male",
                "age_group": "teen",
                "role": "Người được triệu hồi sang dị giới",
                "tone": "Lạc quan, kiên trì, hài hước",
                "tts_voice": "vi-VN-HoaiMyNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Tôi / Tớ', gọi 'Cậu / Bạn / Tiền bối'."
            },
            {
                "speaker_tag": "SPEAKER_01",
                "display_name": "Tiểu Thư Ma Pháp Sư",
                "original_name": "魔法使い (Mage)",
                "aliases": "Tsundere",
                "avatar_color": "#e11d48",
                "gender": "female",
                "age_group": "teen",
                "role": "Bạn đồng hành tài năng",
                "tone": "Tsundere, kiêu kỳ nhưng ấm áp",
                "tts_voice": "vi-VN-HoaiMyNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Tôi', gọi 'Cậu'."
            }
        ],
        "relationships": [
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_01",
                "self_pronoun": "Tớ / Tôi",
                "target_pronoun": "Cậu",
                "relationship_type": "Bạn bè đồng đội",
                "honorific_notes": "Xưng hô trẻ trung tự nhiên phong cách anime."
            },
            {
                "source_speaker": "SPEAKER_01",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Tôi / Tớ",
                "target_pronoun": "Cậu",
                "relationship_type": "Bạn bè đồng đội",
                "honorific_notes": "Quan hệ bạn bè."
            }
        ],
        "terms": [
            {"source_term": "異世界", "target_term": "Dị giới", "category": "LOCATION", "context_note": "Thế giới song song khác"},
            {"source_term": "勇者", "target_term": "Dũng giả", "category": "PROPER_NAME", "context_note": "Anh hùng được triệu hồi cứu thế"},
            {"source_term": "魔王", "target_term": "Ma vương", "category": "PROPER_NAME", "context_note": "Trùm phản diện tối thượng"},
            {"source_term": "冒険者ギルド", "target_term": "Hội mạo hiểm giả", "category": "ORGANIZATION", "context_note": "Tổ chức giao nhận nhiệm vụ săn quái"},
            {"source_term": "魔法使い", "target_term": "Ma pháp sư", "category": "RANK_REALM", "context_note": "Người thi triển phép thuật"},
            {"source_term": "Senpai", "target_term": "Tiền bối", "category": "PROPER_NAME", "context_note": "Đàn anh / Đàn chị khóa trên"},
            {"source_term": "Kouhai", "target_term": "Hậu bối", "category": "PROPER_NAME", "context_note": "Đàn em khóa dưới"},
            {"source_term": "Sensei", "target_term": "Thầy / Cô", "category": "PROPER_NAME", "context_note": "Giáo viên hoặc bác sĩ"},
            {"source_term": "HP", "target_term": "HP", "category": "DO_NOT_TRANSLATE", "context_note": "Điểm sinh mệnh, giữ nguyên"},
            {"source_term": "MP", "target_term": "MP", "category": "DO_NOT_TRANSLATE", "context_note": "Điểm ma lực, giữ nguyên"},
            {"source_term": "EXP", "target_term": "EXP", "category": "DO_NOT_TRANSLATE", "context_note": "Điểm kinh nghiệm thăng cấp"}
        ]
    },
    "modern_business": {
        "id": "modern_business",
        "name": "Đô Thị, Công Sở & Tình Cảm Hiện Đại",
        "icon": "🏢",
        "genre": "Đô Thị / Hiện Đại",
        "description": "Bối cảnh văn phòng, tổng tài bá đạo, công ty thương mại, phim tình cảm đô thị và thuật ngữ kinh doanh hiện đại.",
        "speakers": [
            {
                "speaker_tag": "SPEAKER_00",
                "display_name": "Tổng Giám Đốc",
                "original_name": "总裁 / CEO",
                "aliases": "Sếp, Giám đốc",
                "avatar_color": "#0f172a",
                "gender": "male",
                "age_group": "young_adult",
                "role": "Tổng tài lạnh lùng tài ba",
                "tone": "Dứt khoát, điềm tĩnh, quyền lực",
                "tts_voice": "vi-VN-NamMinhNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Tôi / Anh', gọi 'Cô / Em / Cậu'."
            },
            {
                "speaker_tag": "SPEAKER_01",
                "display_name": "Thư Ký / Trợ Lý",
                "original_name": "助理 / Secretary",
                "aliases": "Trợ lý Linh",
                "avatar_color": "#059669",
                "gender": "female",
                "age_group": "young_adult",
                "role": "Trợ lý đắc lực",
                "tone": "Lịch thiệp, cẩn trọng, chu đáo",
                "tts_voice": "vi-VN-HoaiMyNeural",
                "tts_speed": 1.0,
                "notes": "Xưng 'Em / Tôi', gọi 'Sếp / Giám đốc'."
            }
        ],
        "relationships": [
            {
                "source_speaker": "SPEAKER_00",
                "target_speaker": "SPEAKER_01",
                "self_pronoun": "Tôi / Anh",
                "target_pronoun": "Cô / Em",
                "relationship_type": "Cấp trên - Cấp dưới",
                "honorific_notes": "Lúc làm việc xưng Tôi - Cô, lúc thân mật xưng Anh - Em."
            },
            {
                "source_speaker": "SPEAKER_01",
                "target_speaker": "SPEAKER_00",
                "self_pronoun": "Em / Tôi",
                "target_pronoun": "Sếp / Giám đốc",
                "relationship_type": "Cấp trên - Cấp dưới",
                "honorific_notes": "Gọi sếp tôn kính."
            }
        ],
        "terms": [
            {"source_term": "总裁", "target_term": "Tổng tài / Giám đốc", "category": "PROPER_NAME", "context_note": "Lãnh đạo cao nhất của tập đoàn"},
            {"source_term": "特助", "target_term": "Trợ lý đặc biệt", "category": "PROPER_NAME", "context_note": "Trợ lý thân tín của tổng tài"},
            {"source_term": "董事会", "target_term": "Hội đồng quản trị", "category": "ORGANIZATION", "context_note": "Cơ quan quyền lực của tập đoàn"},
            {"source_term": "商业合同", "target_term": "Hợp đồng thương mại", "category": "SLANG_IDIOM", "context_note": "Thỏa thuận kinh doanh bạc tỷ"},
            {"source_term": "CEO", "target_term": "CEO", "category": "DO_NOT_TRANSLATE", "context_note": "Giữ nguyên chức danh quốc tế"},
            {"source_term": "KPI", "target_term": "KPI", "category": "DO_NOT_TRANSLATE", "context_note": "Chỉ số đánh giá công việc, giữ nguyên"},
            {"source_term": "Deadline", "target_term": "Deadline", "category": "DO_NOT_TRANSLATE", "context_note": "Hạn chót công việc, giữ nguyên"}
        ]
    }
}
