"""单元测试：phase2_bodies 的 body 构造器。

确保：
- top-level keys 数量与 mitm 实录对齐
- flowData / linkData 结构正确
- signInfo / currCompUrl / compUrlPaths 等铁律字段不漏
- 加密字段（entPhone RSA / busiAreaData URL-encoded）格式对
"""
from __future__ import annotations

import json
import urllib.parse

import pytest

from phase2_bodies import (  # type: ignore
    build_basicinfo_save_body,
    build_memberbaseinfo_save_body,
    build_memberpost_save_body,
    build_memberinfo_save_body,
    build_empty_advance_save_body,
    build_pre_electronic_doc_save_body,
    build_ybb_select_save_body,
    build_sl_upload_special_body,
)


class TestBasicInfoSaveBody:
    def test_top_keys_count(self, case_youweifeng):
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="2047094115971878913")
        # 对齐 mitm 实录（42 keys）
        assert len(body) == 42, f"expected 42 keys, got {len(body)}"

    def test_sign_info_fallback_to_constant(self, case_youweifeng):
        """base 没有 signInfo 时 fallback 到 SIGN_INFO_ESTABLISH。"""
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="NAME_ID_X")
        assert body["signInfo"] == "-1607173598"  # fallback

    def test_sign_info_dynamic_from_base(self, case_youweifeng):
        """★铁律：signInfo 是**动态签名**，每个办件 load 返回不同值，save 必须回传。

        这是 2026-04-24 在 case_有为诚 跑通时发现的关键 bug。
        历史样本 load 返回 -1506709975，新案例返回 -2013029225，
        硬编码 -1607173598 会导致 D0022 越权。
        """
        base = {"signInfo": "-2013029225"}
        body = build_basicinfo_save_body(case_youweifeng, base, ent_type="4540", name_id="X")
        assert body["signInfo"] == "-2013029225", (
            "signInfo 必须从 load 响应动态读取，不能硬编码常量"
        )

    def test_sign_info_dynamic_historical_value(self, case_youweifeng):
        """历史值 -1506709975（case_有为风 实录）也应该被透传。"""
        base = {"signInfo": "-1506709975"}
        body = build_basicinfo_save_body(case_youweifeng, base, ent_type="4540", name_id="X")
        assert body["signInfo"] == "-1506709975"

    def test_flow_data_busi_id_is_none(self, case_youweifeng):
        """establish 初次 save 时 busiId 必须是 None（由服务端分配）。"""
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        assert body["flowData"]["busiId"] is None

    def test_flow_data_name_id_propagated(self, case_youweifeng):
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="2047094115971878913")
        assert body["flowData"]["nameId"] == "2047094115971878913"

    def test_ent_name_from_case(self, case_youweifeng):
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        assert "有为风" in body["name"]  # 来自 company_name_phase1_normalized

    def test_ent_phone_is_rsa_base64(self, case_youweifeng):
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        phone = body["entPhone"]
        assert isinstance(phone, str)
        assert len(phone) == 172  # RSA-1024 + Base64 = 172 chars
        # Base64 字符集
        import string
        valid_chars = set(string.ascii_letters + string.digits + "+/=")
        assert all(c in valid_chars for c in phone)

    def test_business_area_plaintext(self, case_youweifeng):
        """businessArea 必须是明文（不能 AES）。"""
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        area = body["businessArea"]
        # 明文中文/数字/符号，不应该是 hex
        assert any("\u4e00" <= c <= "\u9fff" for c in area), "businessArea 应含中文"

    def test_busi_area_data_url_encoded_json(self, case_youweifeng):
        """busiAreaData 必须是 URL-encoded JSON。"""
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        raw = body["busiAreaData"]
        assert raw.startswith("%7B"), f"应该是 URL-encoded JSON 开头（%7B 是 '{{'）"
        decoded = urllib.parse.unquote(raw)
        obj = json.loads(decoded)
        assert "firstPlace" in obj and obj["firstPlace"] == "general"
        assert "param" in obj and isinstance(obj["param"], list)

    def test_no_extra_dto(self, case_youweifeng):
        """mitm 实录 extraDto=None，构造 body 不应传。"""
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        assert "extraDto" not in body

    def test_link_data_save(self, case_youweifeng):
        body = build_basicinfo_save_body(case_youweifeng, {}, ent_type="4540", name_id="X")
        ld = body["linkData"]
        assert ld["compUrl"] == "BasicInfo"
        assert ld["opeType"] == "save"
        assert ld["compUrlPaths"] == ["BasicInfo"]
        assert ld["busiCompUrlPaths"] == "%5B%5D"
        assert ld["continueFlag"] == "continueFlag"


class TestMemberBaseInfoSaveBody:
    """★ 锁定 MemberBaseInfo save body 结构（mitm 实录 MemberBaseInfo__save.json）。

    该 API 在 step 16 组合操作内部调用（BasicInfo save 后，MemberPost save 前），
    服务端借此创建 member 记录分配 itemId。
    """

    @pytest.fixture
    def mbi_load_base(self):
        """模拟 MemberBaseInfo load 响应的 busiData（49 keys 空模板）。"""
        return {
            "flowData": {"busiId": "X", "nameId": "Y", "currCompUrl": "MemberBaseInfo"},
            "linkData": {"continueFlag": "continueFlag", "busiCompComb": {"id": "X"},
                         "compCombArr": ["BasicInfo"]},  # load 返回的脏字段
            "currentLocationVo": {"busiType": "02"},  # load 独有，save 要删
            "fieldList": [{"field": "naturalFlag"}],
            "busiComp": {"id": "647775001"},
            "signInfo": "-2013029225",
            "itemId": "",
            "processVo": None, "jurisdiction": ["x"],
            "name": None, "cerNo": None, "cerType": None,
        }

    def test_top_keys_count_48(self, case_youweifeng, mbi_load_base):
        """sample save body 是 48 keys（load 49 keys - currentLocationVo）。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="NAME_ID_X", busi_id="BID_X",
        )
        assert "currentLocationVo" not in body, "MBI save body 不应含 currentLocationVo"

    def test_link_data_is_clean_5_keys(self, case_youweifeng, mbi_load_base):
        """linkData 必须是 5-key 干净版（不含 load 返回的 busiCompComb/compCombArr/continueFlag）。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        ld = body["linkData"]
        assert set(ld.keys()) == {"compUrl", "opeType", "compUrlPaths",
                                     "busiCompUrlPaths", "token"}
        assert ld["opeType"] == "save"
        assert ld["compUrl"] == "MemberBaseInfo"
        assert ld["compUrlPaths"] == ["MemberPost", "MemberBaseInfo"]

    def test_cerno_is_rsa_encrypted(self, case_youweifeng, mbi_load_base):
        """★ MemberBaseInfo 的 cerNo **必须 RSA 加密**（172 字符 Base64），和 MemberPost 的明文不同。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        cer_no = body["cerNo"]
        assert isinstance(cer_no, str)
        assert len(cer_no) > 100, f"cerNo 应是 RSA 密文（172 字符），实际 {len(cer_no)}"
        assert cer_no != case_youweifeng["person"]["id_no"], "cerNo 不应是明文"

    def test_post_code_order(self, case_youweifeng, mbi_load_base):
        """★ MemberBaseInfo postCode 顺序 = FR05,WTDLR,LLY,CWFZR（和 MemberPost 的 CWFZR,LLY 相反）。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        assert body["postCode"] == "FR05,WTDLR,LLY,CWFZR"

    def test_inv_type_is_null(self, case_youweifeng, mbi_load_base):
        """★ sample 里 invType=null（不是自然人 '1'），对齐样本。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        assert body["invType"] is None

    def test_birthday_inferred_from_id(self, case_youweifeng, mbi_load_base):
        """生日从身份证号自动推断 YYYY-MM-DD。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        # case_有为风 id=450921198812051251 → 1988-12-05
        assert body["birthday"] == "1988-12-05"

    def test_sex_inferred_from_id(self, case_youweifeng, mbi_load_base):
        """性别从身份证倒数第 2 位推断：5=奇=男=1。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        assert body["sexCode"] == "1"

    def test_sign_info_hardcoded(self, case_youweifeng, mbi_load_base):
        """MBI save body signInfo **硬编码** SIGN_INFO_ESTABLISH（和 BasicInfo 的动态不同）。"""
        body = build_memberbaseinfo_save_body(
            case_youweifeng, mbi_load_base,
            ent_type="4540", name_id="X", busi_id="B",
        )
        assert body["signInfo"] == "-1607173598"


class TestMemberPostSaveBody:
    def test_top_keys_count(self, case_youweifeng):
        body = build_memberpost_save_body(case_youweifeng, ent_type="4540", name_id="X")
        assert len(body) == 8  # mitm 实录顶层 8 key

    def test_board_defaults_zero(self, case_youweifeng):
        """个人独资无董事会/监事会。"""
        body = build_memberpost_save_body(case_youweifeng, ent_type="4540", name_id="X")
        assert body["board"] == "0"
        assert body["boardSup"] == "0"

    def test_four_roles(self, case_youweifeng):
        """个人独资 FR05/WTDLR/LLY/CWFZR 四角色都要有成员。"""
        body = build_memberpost_save_body(case_youweifeng, ent_type="4540", name_id="X")
        pk = body["pkAndMem"]
        for role in ("FR05", "WTDLR", "LLY", "CWFZR"):
            assert role in pk
            assert len(pk[role]) == 1
            # ★ mitm 实录顺序：FR05,WTDLR,CWFZR,LLY（非字母序）
            assert pk[role][0]["postCode"] == "FR05,WTDLR,CWFZR,LLY"

    def test_sign_info_establish(self, case_youweifeng):
        body = build_memberpost_save_body(case_youweifeng, ent_type="4540", name_id="X")
        assert body["signInfo"] == "-1607173598"

    def test_member_obj_with_raw_member_is_48_key(self, case_youweifeng):
        """★ 关键锁定：有 raw_member 时每个 role 槽位的 member 对象是 48 key（mitm 实录结构）。

        raw_member 来自 MemberPool/list load 的 list[0]。
        """
        raw_member = {
            "itemId": "2047122552857427968",
            "name": "黄永裕",
            "cerNo": "450921198812051251",
            "cerType": "10",
            "nationalityCode": "156",
            "nationalityCodeName": "中国",
            "naturalFlag": "1",
        }
        body = build_memberpost_save_body(case_youweifeng, raw_member,
                                           ent_type="4540", name_id="X")
        member_obj = body["pkAndMem"]["FR05"][0]
        assert len(member_obj) == 48, f"expected 48 key member obj, got {len(member_obj)}"
        assert member_obj["itemId"] == "2047122552857427968"
        assert member_obj["cerNo"] == "450921198812051251"  # 明文
        assert member_obj["encryptedCerNo"] is None
        assert member_obj["nationalityCode"] == "156"
        assert member_obj["isLoginInfo"] == "1"
        assert isinstance(member_obj["linkData"], dict)
        # 关键 null 元数据字段
        for meta_field in ("flowData", "processVo", "jurisdiction",
                           "busiComp", "signInfo", "extraDto"):
            assert member_obj[meta_field] is None

    def test_member_obj_without_raw_has_default_fallback(self, case_youweifeng):
        """无 raw_member 时 member 对象仍是 48-key 结构（用 case 数据 fallback）。"""
        body = build_memberpost_save_body(case_youweifeng,
                                           ent_type="4540", name_id="X")
        member_obj = body["pkAndMem"]["FR05"][0]
        assert len(member_obj) == 48
        assert member_obj["nationalityCode"] == "156"
        assert member_obj["nationalityCodeName"] == "中国"
        assert member_obj["itemId"] == ""  # 没 raw_member 时为空


class TestEmptyAdvanceBody:
    def test_complement_info(self):
        body = build_empty_advance_save_body("ComplementInfo", ent_type="4540", name_id="X")
        assert body["linkData"]["compUrl"] == "ComplementInfo"
        assert body["flowData"]["currCompUrl"] == "ComplementInfo"
        assert body["signInfo"] == "-1607173598"

    def test_tax_invoice(self):
        body = build_empty_advance_save_body("TaxInvoice", ent_type="4540", name_id="X")
        assert body["linkData"]["compUrl"] == "TaxInvoice"


class TestYbbSelectBody:
    def test_default_0_general_flow(self):
        body = build_ybb_select_save_body({}, ent_type="4540", name_id="X")
        assert body["isSelectYbb"] == "0"
        assert body["isOptional"] == "1"
        assert body["preAuditSign"] == "0"
        assert body["signInfo"] == "-1607173598"

    def test_load_visible_fields_are_preserved(self):
        body = build_ybb_select_save_body(
            {},
            base={"isOptional": "1", "preAuditSign": None, "isSelectYbb": "0"},
            ent_type="4540", name_id="X",
        )
        assert body["isOptional"] == "1"
        assert body["preAuditSign"] == "0"
        assert body["isSelectYbb"] == "0"

    def test_server_flow_and_link_context_are_preserved(self):
        body = build_ybb_select_save_body(
            {},
            base={
                "isOptional": "1",
                "preAuditSign": None,
                "isSelectYbb": "0",
                "itemId": "ITEM-001",
                "signInfo": "1425944578",
                "flowData": {
                    "busiId": "EST-001",
                    "entType": "4540",
                    "busiType": "02",
                    "ywlbSign": "4",
                    "nameId": "NAME-001",
                    "currCompUrl": "YbbSelect",
                    "status": "10",
                },
                "linkData": {
                    "token": "",
                    "continueFlag": None,
                    "compUrl": "YbbSelect",
                    "compUrlPaths": ["YbbSelect"],
                    "busiCompComb": {"id": "COMB-001"},
                    "compCombArr": ["YbbSelect", "PreElectronicDoc"],
                    "opeType": "load",
                    "busiCompUrlPaths": "%5B%5D",
                },
            },
            ent_type="4540",
            name_id="NAME-001",
            busi_id="EST-001",
        )

        assert body["flowData"]["busiId"] == "EST-001"
        assert body["flowData"]["nameId"] == "NAME-001"
        assert body["flowData"]["currCompUrl"] == "YbbSelect"
        assert body["linkData"]["compUrl"] == "YbbSelect"
        assert body["linkData"]["opeType"] == "save"
        assert body["linkData"]["compUrlPaths"] == ["YbbSelect"]
        assert body["linkData"]["busiCompUrlPaths"] == "%5B%5D"
        assert "continueFlag" not in body["linkData"]
        assert "busiCompComb" not in body["linkData"]
        assert "compCombArr" not in body["linkData"]
        assert body["preAuditSign"] == "0"
        assert body["itemId"] == "ITEM-001"
        assert body["signInfo"] == "1425944578"

    def test_case_pre_audit_sign_fills_null_server_value(self):
        body = build_ybb_select_save_body(
            {"preAuditSign": "0"},
            base={
                "isOptional": "1",
                "preAuditSign": None,
                "isSelectYbb": "0",
                "linkData": {"continueFlag": None, "busiCompUrlPaths": "%5B%5D"},
            },
            ent_type="4540",
            name_id="NAME-001",
        )

        assert body["preAuditSign"] == "0"
        assert body["linkData"]["continueFlag"] is None


class TestPreElectronicDocBody:
    def test_server_flow_and_link_context_are_preserved(self):
        body = build_pre_electronic_doc_save_body(
            base={
                "itemId": "ITEM-001",
                "signInfo": "1425944578",
                "flowData": {
                    "busiId": "EST-001",
                    "entType": "4540",
                    "busiType": "02",
                    "ywlbSign": "4",
                    "nameId": "NAME-001",
                    "currCompUrl": "PreElectronicDoc",
                    "status": "10",
                },
                "linkData": {
                    "token": "",
                    "continueFlag": None,
                    "compUrl": "PreElectronicDoc",
                    "compUrlPaths": ["PreElectronicDoc"],
                    "busiCompComb": {"id": "COMB-001"},
                    "compCombArr": ["PreElectronicDoc", "PreSubmitSuccess"],
                    "opeType": "load",
                    "busiCompUrlPaths": "%5B%5D",
                },
            },
            ent_type="4540",
            name_id="NAME-001",
            busi_id="EST-001",
        )

        assert body["flowData"]["busiId"] == "EST-001"
        assert body["flowData"]["currCompUrl"] == "PreElectronicDoc"
        assert body["linkData"]["compUrl"] == "PreElectronicDoc"
        assert body["linkData"]["opeType"] == "save"
        assert body["linkData"]["busiCompComb"] == {"id": "COMB-001"}
        assert body["linkData"]["compCombArr"] == ["PreElectronicDoc", "PreSubmitSuccess"]
        assert body["itemId"] == "ITEM-001"
        assert body["signInfo"] == "1425944578"


class TestSlUploadSpecialBody:
    def test_cerno_lowercase(self):
        """★ 关键铁律：cerno 必须小写 n，大写 N 会触发 A0002。"""
        body = build_sl_upload_special_body(
            file_id="FID",
            mat_code="176",
            mat_name="租赁合同",
            ent_type="4540",
            name_id="X",
        )
        assert "cerno" in body
        assert "cerNo" not in body
        assert body["cerno"] is None

    def test_ope_type_special(self):
        body = build_sl_upload_special_body(
            file_id="FID", mat_code="176", mat_name="租赁合同",
            ent_type="4540", name_id="X",
        )
        assert body["linkData"]["opeType"] == "special"

    def test_item_id_is_mat_code(self):
        body = build_sl_upload_special_body(
            file_id="FID", mat_code="176", mat_name="租赁合同",
            ent_type="4540", name_id="X",
        )
        assert body["itemId"] == "176"

    def test_upload_uuid(self):
        body = build_sl_upload_special_body(
            file_id="my_file_uuid", mat_code="175", mat_name="住所证明",
            ent_type="4540", name_id="X",
        )
        assert body["uploadUuid"] == "my_file_uuid"
