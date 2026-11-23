"""Tests for src/normalize.py (owner: person 1)."""
import unittest

from src.normalize import normalize, normalize_parts, prefix_hints, strip_accents


def toks(s):
    return " ".join(normalize(s))


class TestBasics(unittest.TestCase):
    def test_strip_accents(self):
        self.assertEqual(strip_accents("Đường Nguyễn Huệ"), "Duong Nguyen Hue")

    def test_empty(self):
        self.assertEqual(normalize(""), [])
        self.assertEqual(normalize_parts(""), [])
        self.assertEqual(normalize(" , ;"), [])

    def test_full_address(self):
        self.assertEqual(
            normalize("56/33 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh"),
            ["nam", "ky", "khoi", "nghia", "ben", "thanh", "ho", "chi", "minh"],
        )

    def test_db_entry_and_input_meet(self):
        self.assertEqual(normalize("Phường Bến Thành"), normalize("P. Ben Thanh"))

    def test_tone_placement_and_nfd(self):
        self.assertEqual(toks("Hoà Khánh"), toks("Hòa Khánh"))
        self.assertEqual(toks("Thuỷ Xuân"), toks("Thủy Xuân"))
        self.assertEqual(toks("Hòa Khánh"), toks("Hòa Khánh"))  # NFD input

    def test_i_y_variants(self):
        self.assertEqual(toks("Bùi Sỹ Tiêm"), toks("Bùi Sĩ Tiêm"))
        self.assertEqual(toks("Nam Kỳ"), toks("Nam Kì"))


class TestGluedAndAbbreviated(unittest.TestCase):
    def test_slide5_noise(self):
        self.assertEqual(normalize("X ThuanThanh H. Can Giuoc"), ["thuan", "thanh", "can", "giuoc"])
        self.assertEqual(toks("Thuận Thanh, HCần Giuộc, Tlong An"), "thuan thanh can giuoc long an")

    def test_glued_prefixes(self):
        self.assertEqual(toks("PhườngHòa Cường"), "hoa cuong")
        self.assertEqual(toks("PBồ Đề"), "bo de")
        self.assertEqual(toks("PHòa Cường"), "hoa cuong")
        self.assertEqual(toks("TPĐà Nẵng"), "da nang")
        self.assertEqual(toks("TQuảng Trị"), "quang tri")
        self.assertEqual(toks("TỉnhHưng Yên"), "hung yen")
        self.assertEqual(toks("Thành phốCần Thơ"), "can tho")
        self.assertEqual(toks("TKhánh Hòa"), "khanh hoa")

    def test_dotted_and_undotted(self):
        self.assertEqual(toks("P.Bãi Cháy, T.Quảng Ninh"), "bai chay quang ninh")
        self.assertEqual(toks("TP.Hà Nội"), "ha noi")
        self.assertEqual(toks("P Ninh Kiều, T Lai Châu"), "ninh kieu lai chau")
        self.assertEqual(toks("X. Bình Lư"), "binh lu")

    def test_no_accents_and_caps(self):
        self.assertEqual(toks("PHUONG BEN THANH, THANH PHO HO CHI MINH"), "ben thanh ho chi minh")

    def test_digit_glued_prefix(self):
        self.assertEqual(toks("P3, Q.1"), "3 1")

    def test_special_characters(self):
        self.assertEqual(toks("12 (Nguyễn Huệ) ; P. Bến Nghé"), "nguyen hue ben nghe")


class TestPositionAwarePrefixes(unittest.TestCase):
    def test_names_containing_prefix_words_survive(self):
        self.assertEqual(toks("Bình Dương"), "binh duong")
        self.assertEqual(toks("Cam Đường"), "cam duong")
        self.assertEqual(toks("Thiên Hộ Dương"), "thien ho duong")
        self.assertEqual(toks("Phúc Xá"), "phuc xa")
        self.assertEqual(toks("An Dương Vương"), "an duong vuong")
        self.assertEqual(toks("Huyền Quang"), "huyen quang")
        self.assertEqual(toks("Quán Khái Tây 4"), "quan khai tay 4")
        self.assertEqual(toks("Phượng Hoàng"), "phuong hoang")
        self.assertEqual(toks("Vịnh Thiên Đường 1"), "vinh thien duong 1")
        self.assertEqual(toks("Ánh Dương 2"), "anh duong 2")
        self.assertEqual(toks("Bờ Quan 11"), "bo quan 11")
        self.assertEqual(toks("Tô Hiệu"), "to hieu")

    def test_prefix_at_part_start_removed(self):
        self.assertEqual(toks("Phường Bình Dương"), "binh duong")
        self.assertEqual(toks("Đường An Dương Vương"), "an duong vuong")
        self.assertEqual(toks("Phố Phúc Xá"), "phuc xa")
        self.assertEqual(toks("Tỉnh Lâm Đồng"), "lam dong")

    def test_mid_part_dotted_or_accented_prefix(self):
        self.assertEqual(toks("Phường 12 Quận 5 TP HCM"), "12 5 ho chi minh")
        self.assertEqual(toks("Thuận Thanh H. Can Giuoc"), "thuan thanh can giuoc")

    def test_big_road_words_kept(self):
        self.assertEqual(toks("Đại lộ Bình Dương"), "dai lo binh duong")
        self.assertEqual(toks("Quốc lộ 4D"), "quoc lo 4d")

    def test_country_suffix(self):
        self.assertEqual(toks("Hà Nội, Việt Nam"), "ha noi")
        self.assertEqual(toks("Hà Nội VN"), "ha noi")


class TestHouseNumbers(unittest.TestCase):
    def test_house_and_alley_numbers_removed(self):
        self.assertEqual(toks("42/145/60 Phố An Xá"), "an xa")
        self.assertEqual(toks("268 Trần Hưng Đạo"), "tran hung dao")
        self.assertEqual(toks("Ngõ 76 Phố Yên Phụ"), "yen phu")
        self.assertEqual(toks("Hẻm 50 Quang Trung"), "quang trung")
        self.assertEqual(toks("Kiệt 19 Điện Biên Phủ"), "dien bien phu")
        self.assertEqual(toks("Ngõ 1 Đường An Dương Vương"), "an duong vuong")
        self.assertEqual(toks("Ngách 155 Ngõ 189 Đường Hoàng Hoa Thám"), "hoang hoa tham")
        self.assertEqual(toks("Số nhà 12 Lê Lợi"), "le loi")
        self.assertEqual(toks("74/59 B Đường Âu Cơ"), "au co")

    def test_numbers_inside_names_kept(self):
        self.assertEqual(toks("Hói Kiểng 12"), "hoi kieng 12")
        self.assertEqual(toks("Đồng Bài 3"), "dong bai 3")
        self.assertEqual(toks("Đường B5"), "b5")
        self.assertEqual(toks("D3-5E"), "d3-5e")
        self.assertEqual(toks("1"), "1")
        self.assertEqual(toks("12"), "12")
        self.assertEqual(toks("2 Tháng 9"), "2 thang 9")
        self.assertEqual(toks("107 Đường 3 Tháng 2"), "3 thang 2")

    def test_so_streets(self):
        self.assertEqual(toks("Đường số 8"), "so 8")
        self.assertEqual(toks("467 số 2"), "so 2")
        self.assertEqual(toks("21 Số 4A"), "so 4a")
        self.assertEqual(toks("Đường số 4C"), "so 4c")

    def test_alley_with_so_in_db_entries(self):
        # DB entries that embed an alley prefix reduce to the street name, same as inputs
        self.assertEqual(toks("Hẻm Số 60 Đường Cách Mạng Tháng 8"), "cach mang thang 8")
        self.assertEqual(toks("Ngõ Số 177 Đường Quang Trung"), "quang trung")
        self.assertEqual(toks("Ngõ Hợp Nhất"), toks("Ngách 3 Ngõ Hợp Nhất"))


class TestAliases(unittest.TestCase):
    def test_province_abbreviations(self):
        self.assertEqual(toks("Q1, TP.HCM"), "1 ho chi minh")
        self.assertEqual(toks("TPHCM"), "ho chi minh")
        self.assertEqual(toks("Sài Gòn"), "sai gon".replace("sai gon", "ho chi minh"))
        self.assertEqual(toks("P. Hoàn Kiếm, HN"), "hoan kiem ha noi")
        self.assertEqual(toks("Hải Châu, ĐN"), "hai chau da nang")

    def test_province_alias_not_inside_name(self):
        self.assertEqual(toks("HN Plaza, Hà Nội"), "hn plaza ha noi")

    def test_street_abbreviations(self):
        self.assertEqual(toks("QL1A"), "quoc lo 1a")
        self.assertEqual(toks("QL 13"), "quoc lo 13")
        self.assertEqual(toks("CMT8"), "cach mang thang 8")

    def test_date_streets(self):
        self.assertEqual(toks("Đường 3/2"), "3 thang 2")
        self.assertEqual(toks("2/9"), "2 thang 9")
        self.assertEqual(toks("3/2 Lê Lợi"), "le loi")  # 3/2 is a house number here


class TestParts(unittest.TestCase):
    def test_parts_grouped_by_comma(self):
        self.assertEqual(
            normalize_parts("Hẻm 50 Quang Trung, Phường Ninh Kiều, Thành phố Cần Thơ"),
            [["quang", "trung"], ["ninh", "kieu"], ["can", "tho"]],
        )

    def test_flatten_equals_normalize(self):
        for s in ["P.Bãi Cháy, Quảng Ninh", "21 Số 4A, P Nam Nha Trang, TKhánh Hòa", "a,,b", "Cầu Dứa - Phú Nông"]:
            self.assertEqual(normalize(s), [t for p in normalize_parts(s) for t in p])

    def test_empty_parts_dropped(self):
        self.assertEqual(normalize_parts("A,, ,B"), [["a"], ["b"]])

    def test_dash_separator(self):
        self.assertEqual(normalize_parts("Cầu Dứa - Phú Nông"), [["cau", "dua"], ["phu", "nong"]])

    def test_prefix_hints(self):
        self.assertEqual(
            prefix_hints("Đường Lê Lợi, Phường Bến Nghé, Thành phố Hồ Chí Minh"),
            ["street", "ward", "province"],
        )
        self.assertEqual(prefix_hints("Lê Lợi, H. Bình Chánh, T. Long An"), [None, "district", "province"])
        self.assertEqual(len(prefix_hints("A,,B")), len(normalize_parts("A,,B")))


if __name__ == "__main__":
    unittest.main()
