import pytest
from pathlib import Path


def test_multi_portfolio_crud_and_isolation(isolated_portfolio):
    import tools.portfolio.core as core
    import tools.portfolio.trading as trading
    import tools.portfolio.goals as goals

    # 1. List initial portfolios (should have 'default')
    portfolios = core.list_portfolios()
    assert any(p.id == "default" for p in portfolios)

    # 2. Create emergency fund portfolio
    p_emergency = core.create_portfolio(name="Emergency Fund", portfolio_id="emergency_fund")
    assert p_emergency.id == "emergency_fund"
    assert p_emergency.name == "Emergency Fund"

    # List should now include emergency_fund
    portfolios = core.list_portfolios()
    assert len(portfolios) >= 2
    assert any(p.id == "emergency_fund" for p in portfolios)

    # 3. Add cash to emergency_fund portfolio
    trading.structured_manage_cash_flow(
        amount=100000.0, action="deposit", currency="THB", portfolio_id="emergency_fund"
    )

    # Verify default portfolio has 0 cash THB while emergency_fund has 100000
    state_default = core.get_structured_portfolio_state(portfolio_id="default")
    state_emergency = core.get_structured_portfolio_state(portfolio_id="emergency_fund")

    cash_default = next(h.units for h in state_default.holdings if h.symbol == "CASH_THB")
    cash_emergency = next(h.units for h in state_emergency.holdings if h.symbol == "CASH_THB")

    assert cash_default == 0.0
    assert cash_emergency == 100000.0

    # 4. Create Goals linked to different portfolios
    goals.structured_upsert_goal(
        name="Main Port 10M",
        goal_type="nav_target",
        target_amount_thb=10000000.0,
        portfolio_id="default",
    )
    goals.structured_upsert_goal(
        name="Emergency Cash 100k",
        goal_type="cash_target",
        target_amount_thb=100000.0,
        portfolio_id="emergency_fund",
    )

    all_goals = goals.get_structured_goals()
    g_main = next(g for g in all_goals if g["name"] == "Main Port 10M")
    g_emer = next(g for g in all_goals if g["name"] == "Emergency Cash 100k")

    assert g_main["current_amount_thb"] == 0.0
    assert g_emer["current_amount_thb"] == 100000.0
    assert g_emer["progress_pct"] == 100.0

    # 5. Clean up / delete portfolio
    core.delete_portfolio("emergency_fund")
    portfolios_after = core.list_portfolios()
    assert not any(p.id == "emergency_fund" for p in portfolios_after)


def test_create_portfolio_thai_name_does_not_produce_garbage_id(isolated_portfolio):
    """ชื่อพอร์ตภาษาไทยล้วน (ไม่มี ASCII เลย) ต้อง fallback เป็น id แบบ timestamp
    ไม่ใช่ id ที่เป็นขีดล่างล้วน (regex sub ตัวอักษรไทยทุกตัวเป็น '_') เพราะจะอ่านไม่ออก
    และชนกันได้ง่ายกับชื่อไทยอื่นที่ความยาวเท่ากัน
    """
    import re
    import tools.portfolio.core as core

    p1 = core.create_portfolio(name="พอร์ตเงินสำรองฉุกเฉิน")
    assert p1.name == "พอร์ตเงินสำรองฉุกเฉิน"
    assert re.search(r"[a-zA-Z0-9]", p1.id), f"id ต้องมีตัวอักษร/ตัวเลขจริงอย่างน้อย 1 ตัว ได้ {p1.id!r}"
    assert not re.fullmatch(r"_+", p1.id)

    # ชื่อไทยอีกชื่อที่ความยาวเท่ากันเป๊ะ (คนละความหมาย) ต้องไม่ชน id กับ p1
    p2 = core.create_portfolio(name="พอร์ตกองทุนสำรองบำนาญ")
    assert p2.id != p1.id

    portfolios = core.list_portfolios()
    assert any(p.id == p1.id for p in portfolios)
    assert any(p.id == p2.id for p in portfolios)
