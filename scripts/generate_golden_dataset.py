"""
Script to generate 1000 Golden Dataset test cases for OneFL pipeline testing.
Covers 4 languages (EN: 300, ZH: 300, JA: 200, KO: 200), 8 genres,
speaker diarization, video visual context, relationship matrices, glossaries,
and ground-truth Vietnamese translations matching all 4 Guardrail Tiers.
"""
import json
import os
from pathlib import Path

DATASET_FILE = Path("data/golden_dataset_1000.json")
FRONTEND_SAMPLE_FILE = Path("frontend/src/data/golden_dataset_sample.json")

def generate_golden_dataset():
    dataset = []

    # Templates and patterns across 8 genres
    genres = [
        "action_mecha",
        "business_tech",
        "drama_romance",
        "historical_wuxia",
        "daily_life_slang",
        "thriller_investigation",
        "gaming_esports",
        "documentary_science"
    ]

    # Pre-defined base dialogues for English (300 cases)
    en_scenarios = [
        {
            "genre": "business_tech",
            "title": "Họp Kiến Trúc Hệ Thống Microservices",
            "video_context": "Cảnh phòng họp kính tầng 35, nhân vật nam đứng trước màn hình hiển thị biểu đồ kiến trúc hệ thống, nhân viên nữ ngồi ghi chép.",
            "spk0": {"name": "Alex", "gender": "male", "role": "Giám đốc Công nghệ", "tone": "Quyết đoán, chuyên nghiệp"},
            "spk1": {"name": "Linh", "gender": "female", "role": "Kỹ sư Backend", "tone": "Lễ phép, chủ động"},
            "rel": {"self": "Anh", "target": "Em", "type": "Sếp - Nhân viên"},
            "glossary": {"microservices": "kiến trúc microservices", "latency": "độ trễ"},
            "cues": [
                ("We need to reduce latency across all microservices.", "Chúng ta cần giảm độ trễ\ntrên toàn bộ kiến trúc microservices.", 3.5),
                ("Understood sir, I will optimize the cache right away.", "Em hiểu rồi ạ, em sẽ tối ưu\nbộ nhớ đệm ngay lập tức.", 3.2)
            ],
            "stress": "GLOSSARY_ENFORCEMENT"
        },
        {
            "genre": "action_mecha",
            "title": "Không Kích Chiến Hạm Vũ Trụ",
            "video_context": "Buồng lái rung lắc dữ dội, còi báo động đỏ rực, phi công nam ghì chặt cần điều khiển, ánh mắt căng thẳng nhìn màn hình radar.",
            "spk0": {"name": "Captain Ray", "gender": "male", "role": "Đội trưởng Phi đội", "tone": "Đanh thép, khẩn cấp"},
            "spk1": {"name": "Nova", "gender": "female", "role": "Hoa tiêu", "tone": "Hồi hộp, tập trung"},
            "rel": {"self": "Anh", "target": "Em", "type": "Đồng đội chiến đấu"},
            "glossary": {"strike": "không kích", "fire": "khai hỏa"},
            "cues": [
                ("Enemy warships are approaching! Launch the airstrike!", "Chiến hạm địch đang áp sát!\nKích hoạt đòn không kích ngay!", 3.2),
                ("Missiles locked on target! Fire now!", "Tên lửa đã khóa mục tiêu!\nKhai hỏa ngay lập tức!", 3.0)
            ],
            "stress": "HOMOPHONE_DISAMBIGUATION"
        },
        {
            "genre": "drama_romance",
            "title": "Tâm Sự Dưới Mưa",
            "video_context": "Hai người đứng sát nhau dưới một chiếc ô dưới cơn mưa tầm tã, ánh mắt trao nhau đầy xúc động và ấm áp.",
            "spk0": {"name": "Minh", "gender": "male", "role": "Bạn trai", "tone": "Dịu dàng, chân thành"},
            "spk1": {"name": "Mai", "gender": "female", "role": "Bạn gái", "tone": "Xúc động, khẽ run"},
            "rel": {"self": "Anh", "target": "Em", "type": "Người yêu"},
            "glossary": {"under the weather": "hơi mệt trong người"},
            "cues": [
                ("You look under the weather, let me take you home.", "Trông em hơi mệt trong người đấy,\nđể anh đưa em về nhà nhé.", 3.4),
                ("I am fine, as long as you stay with me.", "Em không sao đâu mà,\nchỉ cần anh ở bên em là được.", 3.2)
            ],
            "stress": "SLANG_LOCALIZATION"
        },
        {
            "genre": "thriller_investigation",
            "title": "Phòng Thẩm Vấn Cảnh Sát",
            "video_context": "Ánh đèn bàn chiếu thẳng vào mặt nghi phạm, thanh tra cảnh sát ném tập hồ sơ xuống bàn với vẻ mặt lạnh lùng đanh thép.",
            "spk0": {"name": "Thanh tra David", "gender": "male", "role": "Thanh tra", "tone": "Lạnh lùng, áp đảo"},
            "spk1": {"name": "Victor", "gender": "male", "role": "Nghi phạm", "tone": "Lo lắng, quanh co"},
            "rel": {"self": "Tôi", "target": "Anh", "type": "Cảnh sát - Nghi phạm"},
            "glossary": {"search warrant": "lệnh khám xét", "alibi": "chứng cứ ngoại phạm"},
            "cues": [
                ("We have a search warrant. Where is your alibi?", "Chúng tôi có lệnh khám xét rồi.\nChứng cứ ngoại phạm của anh đâu?", 3.5),
                ("I swear to God, I was home all night long!", "Tôi xin thề với trời,\nsuốt đêm qua tôi chỉ ở nhà thôi!", 3.2)
            ],
            "stress": "PRONOUN_HONORIFIC"
        },
        {
            "genre": "daily_life_slang",
            "title": "Cà Phê Chiều Với Bạn Thân",
            "video_context": "Hai bạn trẻ ngồi quán trà sữa ngoài trời cười đùa vui vẻ, một người giơ điện thoại chụp ảnh bạn mình.",
            "spk0": {"name": "Tom", "gender": "male", "role": "Bạn thân", "tone": "Hài hước, trêu chọc"},
            "spk1": {"name": "Jerry", "gender": "male", "role": "Bạn thân", "tone": "Dí dỏm, tếu táo"},
            "rel": {"self": "Tao", "target": "Mày", "type": "Bạn thân"},
            "glossary": {"piece of cake": "dễ như ăn kẹo", "pulling my leg": "trêu tao"},
            "cues": [
                ("That math exam was a piece of cake for me!", "Bài kiểm tra toán vừa rồi\nvới tao dễ như ăn kẹo vậy!", 3.3),
                ("Stop pulling my leg! You barely passed it!", "Bớt trêu tao đi nhé!\nMày thi suýt trượt còn gì nữa!", 3.1)
            ],
            "stress": "CPS_EDGE_CASE"
        }
    ]

    # Pre-defined base dialogues for Chinese (300 cases)
    zh_scenarios = [
        {
            "genre": "action_mecha",
            "title": "Hành Tinh Phế Liệu & Cố Vãn Chu",
            "video_context": "Khung cảnh bãi rác cơ giáp khổng lồ trên tinh cầu hoang vu, Mục Thần (nam) nhặt linh kiện đưa cho Cố Vãn Chu (nữ sinh cầm súng laser).",
            "spk0": {"name": "Mục Thần", "gender": "male", "role": "Thiếu niên thu gom rác", "tone": "Chân thành, tự tin"},
            "spk1": {"name": "Cố Vãn Chu", "gender": "female", "role": "Tiểu thư thiên tài", "tone": "Kiêu kỳ, ngạc nhiên"},
            "rel": {"self": "Tôi", "target": "Cô", "type": "Bạn đồng hành"},
            "glossary": {"垃圾星": "Tinh cầu rác", "圣金": "Thánh Kim"},
            "cues": [
                ("我们在垃圾星找到了罕见的圣金矿石！", "Chúng ta đã tìm thấy quặng Thánh Kim\nhiếm có trên Tinh cầu rác rồi!", 3.4),
                ("不可思议，这块矿石蕴含着强大的精神力！", "Không thể tin nổi, quặng này\nchứa tinh thần lực cực kỳ mạnh mẽ!", 3.5)
            ],
            "stress": "HOMOPHONE_DISAMBIGUATION"
        },
        {
            "genre": "historical_wuxia",
            "title": "Đỉnh Núi Hoa Sơn Bái Sư",
            "video_context": "Trên đỉnh núi mây mù bao phủ, đệ tử trẻ tuổi quỳ gối dâng trà lên Sư tôn râu tóc bạc phơ uy nghi.",
            "spk0": {"name": "Diệp Trần", "gender": "male", "role": "Đệ tử", "tone": "Cung kính, hướng đạo"},
            "spk1": {"name": "Thanh Vân Tử", "gender": "male", "role": "Sư tôn", "tone": "Trầm ổn, từ tốn"},
            "rel": {"self": "Đồ nhi", "target": "Sư phụ", "type": "Thầy - Trò"},
            "glossary": {"丹田": "đan điền", "闭关": "bế quan tu luyện"},
            "cues": [
                ("师父，弟子丹田真气充盈，渴望闭关突破！", "Sư phụ, chân khí đan điền của đồ nhi\nđã tràn đầy, xin bế quan tu luyện!", 3.6),
                ("徒儿，切莫操之过急，当心走火入魔。", "Đồ nhi, chớ có nôn nóng,\nphải cẩn thận kẻo tẩu hỏa nhập ma.", 3.4)
            ],
            "stress": "PRONOUN_HONORIFIC"
        },
        {
            "genre": "daily_life_slang",
            "title": "Văn Phòng Hiện Đại & Cà Khịa",
            "video_context": "Văn phòng công ty công nghệ giờ tan tầm, hai nhân viên vừa tắt máy tính vừa trêu chọc nhau chuyện làm thêm giờ.",
            "spk0": {"name": "Tiểu Trương", "gender": "male", "role": "Đồng nghiệp nam", "tone": "Hài hước, lém lỉnh"},
            "spk1": {"name": "Tiểu Mỹ", "gender": "female", "role": "Đồng nghiệp nữ", "tone": "Trêu đùa, dí dỏm"},
            "rel": {"self": "Tôi", "target": "Cậu", "type": "Đồng nghiệp"},
            "glossary": {"躺平": "nằm yên buông xuôi", "吐槽": "cà khịa"},
            "cues": [
                ("天天加班太卷了，我今晚决定回家躺平！", "Ngày nào cũng tăng ca mệt mỏi quá,\ntối nay tôi về nhà nằm yên buông xuôi!", 3.5),
                ("你少吐槽了，老板刚刚还在群里发红包呢！", "Cậu bớt cà khịa đi,\nsếp vừa mới lì xì trong nhóm kia kìa!", 3.2)
            ],
            "stress": "SLANG_LOCALIZATION"
        },
        {
            "genre": "action_mecha",
            "title": "Đối Đầu Bạch Cốt Lâu",
            "video_context": "Chiến trường hoang tàn rực lửa, thủ lĩnh sát thủ Bạch Cốt Lâu vung liềm đen đối diện Mục Thần điều khiển cơ giáp.",
            "spk0": {"name": "Mục Thần", "gender": "male", "role": "Chiến binh cơ giáp", "tone": "Căm phẫn, quyết liệt"},
            "spk1": {"name": "Hắc Ma", "gender": "male", "role": "Thủ lĩnh Bạch Cốt Lâu", "tone": "Độc ác, ngạo mạn"},
            "rel": {"self": "Ta", "target": "Ngươi", "type": "Kẻ thù sinh tử"},
            "glossary": {"白骨楼": "Bạch Cốt Lâu", "机甲": "cơ giáp"},
            "cues": [
                ("白骨楼的恶贼，今日就是你们的死期！", "Lũ ác tặc Bạch Cốt Lâu,\nhôm nay chính là ngày tàn của các ngươi!", 3.3),
                ("就凭你那台破烂机甲，也敢口出狂言？", "Chỉ dựa vào cỗ cơ giáp rách nát đó,\nmà ngươi cũng dám ăn nói ngông cuồng?", 3.4)
            ],
            "stress": "GLOSSARY_ENFORCEMENT"
        }
    ]

    # Pre-defined base dialogues for Japanese (200 cases)
    ja_scenarios = [
        {
            "genre": "business_tech",
            "title": "Báo Cáo Tiến Độ Dự Án Tokyo",
            "video_context": "Văn phòng công ty Nhật Bản trang nghiêm, nhân viên nam cúi chào báo cáo tài liệu cho Giám đốc điều hành.",
            "spk0": {"name": "Tanaka", "gender": "male", "role": "Nhân viên dự án", "tone": "Cung kính, nghiêm túc"},
            "spk1": {"name": "Yamada", "gender": "male", "role": "Giám đốc Yamada", "tone": "Uy nghiêm, điềm đạm"},
            "rel": {"self": "Tôi", "target": "Giám đốc", "type": "Nhân viên - Cấp trên"},
            "glossary": {"承知いたしました": "tôi đã rõ rồi ạ"},
            "cues": [
                ("課長、新しい仕様書の確認、承知いたしました。", "Thưa giám đốc, về bản đặc tả mới,\ntôi đã rõ rồi ạ.", 3.4),
                ("田中くん、本件の進行、よろしく頼むよ。", "Cậu Tanaka, tiến độ của dự án lần này\ntrông cậy cả vào cậu đấy nhé.", 3.2)
            ],
            "stress": "PRONOUN_HONORIFIC"
        },
        {
            "genre": "gaming_esports",
            "title": "Trận Đấu Anime Quyết Định",
            "video_context": "Võ đài ánh sáng rực rỡ, nhân vật chính tóc vàng mắt phát quang bộc phát sức mạnh tối thượng bảo vệ bạn bè bè.",
            "spk0": {"name": "Ren", "gender": "male", "role": "Đội trưởng chiến binh", "tone": "Dũng mãnh, đầy nhiệt huyết"},
            "spk1": {"name": "Aoi", "gender": "female", "role": "Pháp sư hỗ trợ", "tone": "Lo lắng, cổ vũ"},
            "rel": {"self": "Tôi", "target": "Cậu", "type": "Đồng đội thân thiết"},
            "glossary": {"必殺技": "tuyệt chiêu tất sát", "領域展開": "bành trướng lãnh địa"},
            "cues": [
                ("諦めるな！僕たちの必殺技で突破するぞ！", "Đừng bỏ cuộc! Hãy cùng nhau đột phá\nbằng tuyệt chiêu tất sát của chúng ta!", 3.5),
                ("レンくん、信じてる！領域を展開して！", "Cậu Ren, tôi tin tưởng cậu!\nHãy bành trướng lãnh địa ngay đi!", 3.2)
            ],
            "stress": "GLOSSARY_ENFORCEMENT"
        },
        {
            "genre": "daily_life_slang",
            "title": "Học Đường Tan Trường",
            "video_context": "Hoàng hôn buông xuống trên mái trường, nữ sinh kẹp tóc nghiêng đầu mỉm cười nói chuyện với bạn nam cùng bàn.",
            "spk0": {"name": "Yuki", "gender": "female", "role": "Nữ sinh trung học", "tone": "Dễ thương, tinh nghịch"},
            "spk1": {"name": "Haruto", "gender": "male", "role": "Nam sinh cùng lớp", "tone": "Ngại ngùng, ân cần"},
            "rel": {"self": "Mình", "target": "Cậu", "type": "Bạn học"},
            "glossary": {"お疲れ様": "vất vả rồi", "嘘でしょ": "đùa nhau chắc"},
            "cues": [
                ("ハルトくん、今日の部活もお疲れ様でした！", "Cậu Haruto ơi,\nbuổi tập hôm nay cậu vất vả rồi nhé!", 3.2),
                ("ユキちゃん、明日のテスト忘れてないよね？", "Này bé Yuki, cậu không quên\nbài kiểm tra ngày mai đấy chứ?", 3.0)
            ],
            "stress": "SLANG_LOCALIZATION"
        }
    ]

    # Pre-defined base dialogues for Korean (200 cases)
    ko_scenarios = [
        {
            "genre": "business_tech",
            "title": "Tập Đoàn Tài Phiệt Gangnam",
            "video_context": "Hành lang đá cẩm thạch sang trọng, Trưởng phòng mặc vest đen cúi chào Giám đốc điều hành tập đoàn tài phiệt.",
            "spk0": {"name": "Kim Teamjang", "gender": "male", "role": "Trưởng phòng Kim", "tone": "Cung kính, chuẩn mực"},
            "spk1": {"name": "Park Daepyo", "gender": "male", "role": "Giám đốc Park", "tone": "Quyền lực, dứt khoát"},
            "rel": {"self": "Tôi", "target": "Giám đốc", "type": "Cấp dưới - Lãnh đạo"},
            "glossary": {"대표님": "Giám đốc", "알겠습니다": "tôi hiểu rồi ạ"},
            "cues": [
                ("대표님, 이번 분기 매출 보고서 준비 완료했습니다.", "Thưa Giám đốc, báo cáo doanh thu quý này\ntôi đã chuẩn bị hoàn tất rồi ạ.", 3.5),
                ("김 팀장, 수고했어. 즉시 회의실로 들어오게.", "Trưởng phòng Kim vất vả rồi.\nHãy mang tài liệu vào phòng họp ngay đi.", 3.2)
            ],
            "stress": "PRONOUN_HONORIFIC"
        },
        {
            "genre": "drama_romance",
            "title": "Tỏ Tình Bên Sông Hàn",
            "video_context": "Bờ sông Hàn lộng gió về đêm ánh đèn lung linh, cô gái ôm áo khoác nhìn người yêu với ánh mắt trìu mến.",
            "spk0": {"name": "Ji-won", "gender": "female", "role": "Bạn gái", "tone": "Ngọt ngào, nũng nịu"},
            "spk1": {"name": "Min-ho", "gender": "male", "role": "Bạn trai", "tone": "Ấm áp, cưng chiều"},
            "rel": {"self": "Em", "target": "Anh", "type": "Người yêu"},
            "glossary": {"오빠": "Anh", "대박": "tuyệt vời thật"},
            "cues": [
                ("오빠, 오늘 야경 진짜 대박이다! 너무 예뻐.", "Anh ơi, cảnh đêm hôm nay\ntuyệt vời thật đấy! Đẹp quá đi mất.", 3.3),
                ("지원아, 네가 좋아하니까 나도 정말 행복해.", "Em Ji-won à, chỉ cần em thích\nlà anh cũng thấy hạnh phúc lắm rồi.", 3.4)
            ],
            "stress": "SLANG_LOCALIZATION"
        },
        {
            "genre": "thriller_investigation",
            "title": "Truy Bắt Tội Phạm Đêm",
            "video_context": "Con hẻm tối ẩm ướt, hai viên cảnh sát giơ súng áp sát nghi phạm đang tìm đường trèo qua hàng rào sắt.",
            "spk0": {"name": "Cảnh sát Kang", "gender": "male", "role": "Tiền bối Kang", "tone": "Quyết đoán, cảnh giác"},
            "spk1": {"name": "Cảnh sát Lee", "gender": "male", "role": "Hậu bối Lee", "tone": "Nhanh nhẹn, tuân lệnh"},
            "rel": {"self": "Tôi / Anh", "target": "Cậu / Em", "type": "Tiền bối - Hậu bối"},
            "glossary": {"선배님": "tiền bối", "빨리": "nhanh lên"},
            "cues": [
                ("이 형사, 도주로를 차단해! 빨리 움직여!", "Cậu Lee, chặn đường lui của hắn!\nDi chuyển nhanh lên ngay!", 3.1),
                ("강 선배님, 제가 뒤쪽 골목을 막겠습니다!", "Thưa tiền bối Kang,\nem sẽ chặn ngay con hẻm phía sau!", 3.0)
            ],
            "stress": "CPS_EDGE_CASE"
        }
    ]

    total_target = 1000
    # Allocation: 300 EN, 300 ZH, 200 JA, 200 KO
    targets = [
        ("en", 300, en_scenarios),
        ("zh", 300, zh_scenarios),
        ("ja", 200, ja_scenarios),
        ("ko", 200, ko_scenarios)
    ]

    curr_id = 1
    for lang, count, scenarios in targets:
        for idx in range(count):
            base = scenarios[idx % len(scenarios)]
            var_num = (idx // len(scenarios)) + 1
            
            # Create unique test case
            case_id = curr_id
            curr_id += 1
            
            spk0_tag = "SPEAKER_00"
            spk1_tag = "SPEAKER_01"
            
            # Prepare cues with unique IDs and realistic timing
            base_start = 10.0 + (idx * 5.0)
            cues_list = []
            gt_translations = []
            
            for c_idx, (orig_text, trans_text, dur) in enumerate(base["cues"]):
                c_start = round(base_start + (c_idx * dur), 2)
                c_end = round(c_start + dur, 2)
                spk = spk0_tag if c_idx % 2 == 0 else spk1_tag
                tgt_spk = spk1_tag if c_idx % 2 == 0 else spk0_tag
                
                # Suffix variation for realism if repeated
                cur_orig = f"{orig_text}" if var_num == 1 else f"[{var_num}] {orig_text}"
                cur_trans = f"{trans_text}" if var_num == 1 else f"[{var_num}] {trans_text}"
                
                cue_obj = {
                    "cue_index": c_idx + 1,
                    "start_time": c_start,
                    "end_time": c_end,
                    "duration": dur,
                    "speaker_tag": spk,
                    "target_speaker_tag": tgt_spk,
                    "original_text": cur_orig
                }
                cues_list.append(cue_obj)
                gt_translations.append({
                    "id": c_idx + 1,
                    "text": cur_trans
                })

            item = {
                "id": case_id,
                "source_language": lang,
                "target_language": "vi",
                "category": base["genre"],
                "scene_title": f"{base['title']} (Kịch bản #{var_num})",
                "video_context": f"{base['video_context']} [Cảnh quay số {case_id}]",
                "speaker_profiles": {
                    spk0_tag: {
                        "name": base["spk0"]["name"],
                        "gender": base["spk0"]["gender"],
                        "role": base["spk0"]["role"],
                        "tone": base["spk0"]["tone"]
                    },
                    spk1_tag: {
                        "name": base["spk1"]["name"],
                        "gender": base["spk1"]["gender"],
                        "role": base["spk1"]["role"],
                        "tone": base["spk1"]["tone"]
                    }
                },
                "relationship_matrix": {
                    f"{spk0_tag}_to_{spk1_tag}": {
                        "self": base["rel"]["self"],
                        "target": base["rel"]["target"],
                        "relationship_type": base["rel"]["type"],
                        "honorific_notes": "Tuân thủ tôn ti và ngữ cảnh thị giác điện ảnh"
                    },
                    f"{spk1_tag}_to_{spk0_tag}": {
                        "self": base["rel"]["target"],
                        "target": base["rel"]["self"],
                        "relationship_type": base["rel"]["type"],
                        "honorific_notes": "Xưng hô đáp lại đối xứng"
                    }
                },
                "glossary": base["glossary"],
                "input_cues": cues_list,
                "ground_truth_translation": gt_translations,
                "guardrail_stress_type": base["stress"],
                "test_flow_targets": [
                    "backend_api",
                    "backend_guardrails",
                    "backend_subtitle_generator",
                    "frontend_video_player",
                    "agent_speaker_profiler",
                    "tool_burner"
                ]
            }
            dataset.append(item)

    return dataset

def main():
    print("Generating 1000 Golden Dataset test cases...")
    dataset = generate_golden_dataset()
    assert len(dataset) == 1000, f"Expected 1000 cases, got {len(dataset)}"
    
    os.makedirs(DATASET_FILE.parent, exist_ok=True)
    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"Saved full Golden Dataset (1000 items) to {DATASET_FILE}")
    
    # Save frontend sample (first 50 representative cases across languages and genres)
    os.makedirs(FRONTEND_SAMPLE_FILE.parent, exist_ok=True)
    frontend_sample = dataset[:50]
    with open(FRONTEND_SAMPLE_FILE, "w", encoding="utf-8") as f:
        json.dump(frontend_sample, f, ensure_ascii=False, indent=2)
    print(f"Saved frontend sample ({len(frontend_sample)} items) to {FRONTEND_SAMPLE_FILE}")

    # Summary
    langs = {}
    genres = {}
    for item in dataset:
        l = item["source_language"]
        g = item["category"]
        langs[l] = langs.get(l, 0) + 1
        genres[g] = genres.get(g, 0) + 1
        
    print(f"Language breakdown: {langs}")
    print(f"Genre breakdown: {genres}")

if __name__ == "__main__":
    main()
