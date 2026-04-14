"""测试"我的自选"功能的完整流程"""
from typing import List

# 模拟从数据库获取的数据（根据 VPS 实际数据）
RAW_UID = "105.TLT_105.QQQ_107.EEM_105.JEPQ_107.EWJ_105.MCHI_107.IWM_107.NLR_107.URA_107.GDXJ_107.GLD_107.GDX_107.SLV_107.ARKK_105.BKCH_105.DTCR_107.KWEB_107.CQQQ"

def convert_list(input_list: List[str]) -> List[str]:
    """复制自 utils/utils.py 的 convert_list"""
    result = []
    for item in input_list:
        if "." not in item and result:  # 当前项不含点且结果列表不为空
            result[-1] += "_" + item  # 合并到前一项
        else:
            result.append(item)  # 正常添加项
    input_list = result
    return input_list


def test_convert_list():
    """测试 convert_list 的行为"""
    print("=" * 80)
    print("测试 convert_list 函数")
    print("=" * 80)
    
    # 情况 1: get_uid_list_by_game 返回单个字符串（未拆分）
    print("\n【情况 1】返回单个字符串（未拆分）:")
    uid_list_1 = [RAW_UID]
    print(f"输入: {uid_list_1}")
    print(f"输入长度: {len(uid_list_1)}")
    result_1 = convert_list(uid_list_1)
    print(f"输出: {result_1}")
    print(f"输出长度: {len(result_1)}")
    
    # 情况 2: get_uid_list_by_game 返回已拆分的列表
    print("\n【情况 2】返回已拆分的列表:")
    uid_list_2 = RAW_UID.split('_')
    print(f"输入: {uid_list_2[:5]}... (共 {len(uid_list_2)} 个)")
    print(f"输入长度: {len(uid_list_2)}")
    result_2 = convert_list(uid_list_2)
    print(f"输出: {result_2[:5]}... (共 {len(result_2)} 个)")
    print(f"输出长度: {len(result_2)}")
    
    # 情况 3: 如果数据库存储时已经用 _ 连接，get_uid_list_by_game 可能返回什么？
    print("\n【情况 3】模拟 gsuid_core 的 get_uid_list_by_game 返回值:")
    print("需要查看 gsuid_core 源码确认返回格式...")
    
    # 分析
    print("\n" + "=" * 80)
    print("分析结论:")
    print("=" * 80)
    print(f"原始数据包含 {len(RAW_UID.split('_'))} 个股票")
    print(f"如果 get_uid_list_by_game 返回 ['{RAW_UID[:30]}...']，convert_list 后仍然是 1 个元素")
    print(f"这会导致只渲染 1 个股票，而不是 18 个！")


if __name__ == "__main__":
    test_convert_list()
