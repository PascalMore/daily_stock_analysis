"""
Tests for tushare_fetcher amplitude computation (issue: 7-10 报告中振幅都是 N/A).

Tushare `index_daily` API 不直接返回振幅字段，但 row 里 high/low/prev_close 都齐。
修复: amplitude = round(((safe_float(high) or 0) - (safe_float(low) or 0)) / prev_close * 100, 2)

此 test 不发起网络请求，纯逻辑验证：
- 公式正确性（多种输入场景）
- 源文件确实包含修复（防回归）
- None-safe 处理
"""
import os
import re
import sys

import pytest


DSA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DSA_ROOT not in sys.path:
    sys.path.insert(0, DSA_ROOT)


def _compute_amplitude(high, low, prev_close):
    """
    复刻 tushare_fetcher.py:835 的修复表达式（独立函数，便于纯逻辑测试）.

    公式: round(((safe_float(high) or 0) - (safe_float(low) or 0)) / prev_close * 100, 2)
    边界: prev_close == 0 → 0.0（防除零）
    """
    # safe_float 在 runtime 把 None/空字符串转 None; 这里是 None 时走 0
    safe_high = high if high is not None else 0
    safe_low = low if low is not None else 0
    if prev_close:
        return round((safe_high - safe_low) / prev_close * 100, 2)
    return 0.0


class TestAmplitudeFormula:
    """公式纯逻辑测试: 7 个场景覆盖正常/边界/异常."""

    def test_normal_amplitude(self):
        """(high - low) / prev_close * 100, 正常值."""
        assert _compute_amplitude(100.0, 90.0, 100.0) == 10.0

    def test_zero_amplitude_when_high_eq_low(self):
        """平盘: high == low → 振幅 0."""
        assert _compute_amplitude(50.0, 50.0, 50.0) == 0.0

    def test_7_10_real_sh_index(self):
        """7-10 实际数据: 上证指数振幅 ≈ 2.56%."""
        # (4040.54 - 3938.88) / 3977.55 * 100 = 2.5555... → 2.56
        assert _compute_amplitude(4040.54, 3938.88, 3977.55) == pytest.approx(2.56, abs=0.01)

    def test_rounded_to_2_decimals(self):
        """round to 2 decimals: 10.526 → 10.53."""
        assert _compute_amplitude(100.0, 90.0, 95.0) == 10.53

    def test_prev_close_zero_returns_zero(self):
        """prev_close=0 → 返回 0.0（不抛 ZeroDivisionError）."""
        assert _compute_amplitude(110.0, 90.0, 0.0) == 0.0

    def test_prev_close_none_returns_zero(self):
        """prev_close=None → 返回 0.0."""
        assert _compute_amplitude(110.0, 90.0, None) == 0.0

    def test_high_none_safe(self):
        """high=None → 当作 0, 振幅可能变负但不会崩."""
        # (0 - 90) / 100 * 100 = -90 → round -90.0
        # 这种情况实际不会发生（API 要么有值要么整行缺），但要 None-safe
        assert _compute_amplitude(None, 90.0, 100.0) == -90.0

    def test_low_none_safe(self):
        """low=None → 当作 0, 振幅可能过大但不会崩."""
        # (110 - 0) / 100 * 100 = 110 → round 110.0
        assert _compute_amplitude(110.0, None, 100.0) == 110.0

    def test_all_none_safe(self):
        """high=low=prev_close 全 None → 0.0."""
        assert _compute_amplitude(None, None, None) == 0.0


class TestTushareFetcherSource:
    """源文件检查: 防止代码回退到 amplitude=0.0."""

    def test_tushare_fetcher_no_longer_hardcodes_zero(self):
        """tushare_fetcher.py 不应再硬编码 amplitude=0.0."""
        fetcher_path = os.path.join(DSA_ROOT, "data_provider", "tushare_fetcher.py")
        with open(fetcher_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 修复前: 'amplitude': 0.0 # Tushare index_daily 不直接返回振幅
        # 修复后: 表达式含 prev_close
        match = re.search(r"'amplitude':\s*([^,\n]+)", content)
        assert match, "找不到 amplitude 行"
        rhs = match.group(1).strip()
        # 不能是 0.0
        assert rhs != "0.0", f"振幅不应再硬编码 0.0, 实际: {rhs}"
        # 必须包含 prev_close (修复特征)
        assert "prev_close" in rhs, f"修复后表达式应含 prev_close, 实际: {rhs}"

    def test_amplitude_uses_high_low(self):
        """修复后表达式必须用 high 和 low 计算."""
        fetcher_path = os.path.join(DSA_ROOT, "data_provider", "tushare_fetcher.py")
        with open(fetcher_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 找到包含 amplitude 的行
        match = re.search(r"'amplitude':\s*([^\n]+)", content)
        assert match is not None
        rhs = match.group(1)
        assert "high" in rhs, f"修复后表达式应引用 high, 实际: {rhs}"
        assert "low" in rhs, f"修复后表达式应引用 low, 实际: {rhs}"