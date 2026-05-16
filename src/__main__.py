"""
两相制冷剂等效单相物性计算工具（针对温度滑移区间的等效气相建模）
基于 REFPROP 物性数据库，采用对称模型（EMT）计算等效导热系数，
支持 McAdams 或 Cicchitti 粘度模型，并提供多种等效比热容方法。

重要说明：
    对于仿真软件中需要将两相混合物等效为气态制冷剂的场景，
    推荐使用 cp_method = 'weighted' 或自定义 'enthalpy_based' 方法，
    而 不推荐 直接使用饱和气比热容 ('gas')，因为后者忽略了
    两相区温度滑移和实际焓变。
"""

import os
import numpy as np
import pandas as pd
from ctREFPROP.ctREFPROP import REFPROPFunctionLibrary
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

console = Console()


def calculate_equivalent_thermal_conductivity(λ_l, λ_v, φ_v):
    """
    采用 EMT（Effective Medium Theory）对称模型计算两相混合物的等效导热系数。
    原理：假设液相和气相随机均匀分布，有效导热系数 λ_eq 满足：
        (1-φ_v)*(λ_l - λ_eq)/(λ_l + 2λ_eq) + φ_v*(λ_v - λ_eq)/(λ_v + 2λ_eq) = 0
    整理得二次方程：a λ_eq^2 + b λ_eq + c = 0，其中：
        a = 1
        b = 2(1-φ_v)λ_v - (1-φ_v)λ_l + 2φ_v λ_l - φ_v λ_v
        c = -2 λ_l λ_v
    选取介于 λ_l 和 λ_v 之间的物理根作为等效导热系数。

    参数:
        λ_l : 液相导热系数 (W/m·K)
        λ_v : 气相导热系数 (W/m·K)
        φ_v : 气相体积分数 (0~1)

    返回:
        λ_eq : 等效导热系数 (W/m·K)
    """
    if φ_v <= 1e-10:
        return λ_l
    if φ_v >= 1.0 - 1e-10:
        return λ_v

    a = 1.0
    b = 2 * (1 - φ_v) * λ_v - (1 - φ_v) * λ_l + 2 * φ_v * λ_l - φ_v * λ_v
    c = -2 * λ_l * λ_v

    discriminant = b**2 - 4 * a * c
    sqrt_d = np.sqrt(discriminant)
    λ_eq1 = (-b + sqrt_d) / (2 * a)
    λ_eq2 = (-b - sqrt_d) / (2 * a)

    λ_min = min(λ_l, λ_v)
    λ_max = max(λ_l, λ_v)
    if λ_min - 1e-10 <= λ_eq1 <= λ_max + 1e-10:
        return λ_eq1
    else:
        return λ_eq2


def calculate_equivalent_viscosity(μ_l, μ_v, Q, φ_v, model='mcadams'):
    """
    计算两相混合物的等效动力粘度。
    支持两种常用经验模型：

    1. McAdams 模型（调和平均）：
        1/μ_eq = (1-Q)/μ_l + Q/μ_v
        基于质量含气率 Q，适用于常规两相流压降计算。

    2. Cicchitti 模型（体积加权算术平均）：
        μ_eq = (1-φ_v) μ_l + φ_v μ_v
        基于气相体积分数 φ_v，适用于高流速均匀流动。

    参数:
        μ_l  : 液相动力粘度 (Pa·s)
        μ_v  : 气相动力粘度 (Pa·s)
        Q    : 质量含气率（干度，0~1）
        φ_v  : 气相体积分数（仅 cicchitti 模型需要）
        model: 模型选择，'mcadams' 或 'cicchitti'

    返回:
        μ_eq : 等效动力粘度 (Pa·s)
    """
    if Q <= 1e-10:
        return μ_l
    if Q >= 1.0 - 1e-10:
        return μ_v

    if model == 'mcadams':
        return 1 / ((1 - Q) / μ_l + Q / μ_v)
    elif model == 'cicchitti':
        return (1 - φ_v) * μ_l + φ_v * μ_v
    else:
        raise ValueError("不支持的粘度模型，可选'mcadams'或'cicchitti'")


def safe_refprop_call(RP, fluid, inputs, outputs, units, iMass, iFlag, prop1, prop2, z):
    """
    安全调用REFPROP底层DLL，忽略特定无害警告（如接近临界点时迭代轻微不收敛）。
    REFPROP返回的ierr含义：
        ierr < 0 : 警告（计算结果仍可用，忽略代码-319, -320, -113）
        ierr > 0 : 严重错误，中止计算

    参数:
        RP     : REFPROPFunctionLibrary实例
        fluid  : 流体名称
        inputs : 输入类型，如"PQ"
        outputs: 输出变量字符串，分号分隔
        units  : 单位制（如RP.MASS_BASE_SI）
        iMass  : 质量基标志
        iFlag  : 标志位
        prop1, prop2 : 输入变量值
        z      : 组分数组（纯流体为空列表）

    返回:
        res : REFPROP返回对象
    """
    res = RP.REFPROPdll(fluid, inputs, outputs, units, iMass, iFlag, prop1, prop2, z)
    if res.ierr < 0:
        if res.ierr not in [-319, -320, -113]:
            warn_text = Text()
            warn_text.append("[WARN] REFPROP警告 (", style="yellow")
            warn_text.append(f"ierr={res.ierr}", style="cyan")
            warn_text.append("): ", style="yellow")
            warn_text.append(f"{res.herr}", style="dim")
            console.print(warn_text)
    elif res.ierr > 0:
        raise Exception(f"REFPROP错误 (ierr={res.ierr}): {res.herr}")
    return res


def get_single_prop(RP, fluid, p_Pa, Q, prop_name):
    """
    通过压力(P) + 质量干度(Q) 输入，获取单个物性值（SI单位）。
    参数:
        prop_name: 性质代码，如 "T", "D", "H", "CPVAP", "CPLIQ" 等
    """
    res = safe_refprop_call(RP, fluid, "PQ", prop_name, RP.MASS_BASE_SI, 0, 0, p_Pa, Q, [])
    return res.Output[0]


def get_transport_single_phase(RP, fluid, p_Pa, Q_phase):
    """
    获取纯液相 (Q=0) 或纯气相 (Q=1) 的输运性质（导热系数、动力粘度）。
    注：同一压力下，饱和液与饱和气温度不同，但输运性质只与压力及相态有关。
    """
    res = safe_refprop_call(RP, fluid, "PQ", "TCX;VIS", RP.MASS_BASE_SI, 0, 0, p_Pa, Q_phase, [])
    return res.Output[0], res.Output[1]


def generate_single_pressure_table(RP, fluid, p_MPa, n_points=20,
                                   μ_model='mcadams', cp_method='weighted'):
    """
    生成指定压力下饱和两相区（干度 0→1）的等效物性数据表，适用于将两相混合物
    等效为单一“气相”用于仿真软件。

    等效原理：
        - 密度：直接使用 REFPROP 给出的混合物密度（真实密度）
        - 导热系数：EMT 对称模型
        - 动力粘度：McAdams 或 Cicchitti 模型
        - 比热容：支持三种方法
            * 'weighted' (推荐) : (1-Q)*CP_LIQ + Q*CP_VAP
            * 'enthalpy_based' : (h_mix - h_liq_sat@T_bubble) / (T_mix - T_bubble)
            * 'gas' (不推荐)   : 直接使用饱和气比热容 CP_VAP（忽略温度滑移）

    对于仿真软件的气相物性，推荐使用 'weighted' 或 'enthalpy_based'，
    因为 'gas' 方法会导致等效气体在温度滑移区间的吸热量严重失真。

    参数:
        RP        : REFPROPFunctionLibrary 实例
        fluid     : 流体名称
        p_MPa     : 压力 (MPa)
        n_points  : 干度离散点数
        μ_model   : 粘度模型 ('mcadams' 或 'cicchitti')
        cp_method : 比热容方法 ('weighted', 'enthalpy_based', 'gas')

    返回:
        df        : DataFrame，包含温度、干度、密度、等效比热容、等效导热率、
                    等效动力粘度、焓值等
        T_bubble  : 泡点温度 (℃)
        T_dew     : 露点温度 (℃)
    """
    p_Pa = p_MPa * 1_000_000

    # 泡点/露点温度（K）
    T_bubble_K = get_single_prop(RP, fluid, p_Pa, 0.0, "T")
    T_dew_K    = get_single_prop(RP, fluid, p_Pa, 1.0, "T")
    T_bubble = T_bubble_K - 273.15
    T_dew    = T_dew_K - 273.15

    if T_dew <= T_bubble:
        raise ValueError(f"温度滑移异常：露点({T_dew:.2f}℃) ≤ 泡点({T_bubble:.2f}℃)")

    temp_text = Text()
    temp_text.append("  泡点: ", style="dim")
    temp_text.append(f"{T_bubble:.2f}℃", style="blue")
    temp_text.append(", 露点: ", style="dim")
    temp_text.append(f"{T_dew:.2f}℃", style="blue")
    temp_text.append(", 滑移: ", style="dim")
    temp_text.append(f"{T_dew - T_bubble:.2f}℃", style="cyan")
    console.print(temp_text)

    # 预先获取泡点下的饱和液焓（用于 enthalpy_based 方法）
    h_sat_liq_bubble = get_single_prop(RP, fluid, p_Pa, 0.0, "H") if cp_method == 'enthalpy_based' else None

    # 预先获取固定的饱和相性质（同一压力下与干度无关）
    THC_L, VIS_L = get_transport_single_phase(RP, fluid, p_Pa, 0.0)
    THC_V, VIS_V = get_transport_single_phase(RP, fluid, p_Pa, 1.0)
    CP_L = get_single_prop(RP, fluid, p_Pa, 0.0, "CPLIQ")  # 饱和液比热容
    CP_V = get_single_prop(RP, fluid, p_Pa, 1.0, "CPVAP")  # 饱和气比热容
    D_L = get_single_prop(RP, fluid, p_Pa, 0.0, "DLIQ")    # 液相密度
    D_V = get_single_prop(RP, fluid, p_Pa, 1.0, "DVAP")    # 气相密度

    prop_text = Text()
    prop_text.append("  物性核对: ", style="dim")
    prop_text.append(f"THC_L={THC_L:.4f}", style="green")
    prop_text.append(", ", style="dim")
    prop_text.append(f"THC_V={THC_V:.4f}", style="green")
    prop_text.append(", ", style="dim")
    prop_text.append(f"VIS_L={VIS_L:.2e}", style="magenta")
    prop_text.append(", ", style="dim")
    prop_text.append(f"VIS_V={VIS_V:.2e}", style="magenta")
    console.print(prop_text)

    if any(np.isnan([CP_L, CP_V, D_L, D_V, THC_L, THC_V, VIS_L, VIS_V])):
        raise ValueError("REFPROP返回了NaN值")

    Q_points = np.linspace(0, 1, n_points)
    data = []

    for Q in Q_points:
        try:
            # ----- 混合物性质 -----
            T_mix_K = get_single_prop(RP, fluid, p_Pa, Q, "T")      # 混合物温度
            H_mix   = get_single_prop(RP, fluid, p_Pa, Q, "H")      # 混合物焓
            ρ_eq    = get_single_prop(RP, fluid, p_Pa, Q, "D")      # 混合物真实密度

            # ----- 气相体积分数 φ_v -----
            if Q <= 1e-10:
                φ_v = 0.0
            elif Q >= 1.0 - 1e-10:
                φ_v = 1.0
            else:
                v_l = 1 / D_L
                v_v = 1 / D_V
                v_mix = (1 - Q) * v_l + Q * v_v
                φ_v = Q * v_v / v_mix

            # ----- 等效物性 -----
            λ_eq = calculate_equivalent_thermal_conductivity(THC_L, THC_V, φ_v)
            μ_eq = calculate_equivalent_viscosity(VIS_L, VIS_V, Q, φ_v, model=μ_model)

            # ----- 等效比热容（关键：适用于仿真软件的气相等效）-----
            if cp_method == 'weighted':
                cp_eq = (1 - Q) * CP_L + Q * CP_V
            elif cp_method == 'enthalpy_based':
                # 基于焓差的等效比热容：从泡点饱和液加热到当前混合物温度所需的平均热容
                delta_T = T_mix_K - T_bubble_K
                if delta_T <= 1e-6:
                    cp_eq = CP_L   # 接近泡点时使用液相比热
                else:
                    cp_eq = (H_mix - h_sat_liq_bubble) / delta_T
            elif cp_method == 'gas':
                # 不推荐：直接使用饱和气比热容
                cp_eq = CP_V
            else:
                raise ValueError("cp_method 必须为 'weighted', 'enthalpy_based' 或 'gas'")

            # ----- 合理性检查 -----
            if not (min(THC_L, THC_V) - 1e-10 <= λ_eq <= max(THC_L, THC_V) + 1e-10):
                warn_text = Text()
                warn_text.append("[WARN] ", style="yellow")
                warn_text.append(f"Q={Q:.3f}", style="cyan")
                warn_text.append(" 等效导热率异常: ", style="yellow")
                warn_text.append(f"{λ_eq:.6f}", style="red")
                warn_text.append(" (液:", style="dim")
                warn_text.append(f"{THC_L:.4f}", style="green")
                warn_text.append(", 气:", style="dim")
                warn_text.append(f"{THC_V:.4f}", style="green")
                warn_text.append(")", style="dim")
                console.print(warn_text)

            data.append({
                '干度Q': Q,
                '温度(℃)': T_mix_K - 273.15,
                '密度(kg/m³)': ρ_eq,
                '焓值(J/kg)': H_mix,
                '饱和液比热容(J/kg-K)': CP_L,
                '饱和气比热容(J/kg-K)': CP_V,
                '等效导热率(W/m-K)': λ_eq,
                '等效动力粘度(Pa-s)': μ_eq,
                '等效比热容(J/kg-K)': cp_eq
            })

        except Exception as e:
            err_text = Text()
            err_text.append("[WARN] ", style="yellow")
            err_text.append(f"干度Q={Q:.3f}", style="cyan")
            err_text.append("计算失败: ", style="yellow")
            err_text.append(f"{e}", style="red")
            console.print(err_text)
            continue

    if len(data) < 2:
        raise Exception("有效数据点不足，无法生成物性表")

    df = pd.DataFrame(data)
    df = df.sort_values('干度Q').reset_index(drop=True)

    # 列顺序整理
    df = df[[
        '温度(℃)', '干度Q', '密度(kg/m³)', '等效比热容(J/kg-K)',
        '等效导热率(W/m-K)', '等效动力粘度(Pa-s)', '焓值(J/kg)',
        '饱和液比热容(J/kg-K)', '饱和气比热容(J/kg-K)'
    ]]

    return df, T_bubble, T_dew


def get_refprop_path():
    """
    检查并获取REFPROP路径，支持环境变量和用户输入。
    """
    default_path = os.environ.get('RPPREFIX', None)
    common_paths = [
        default_path,
        'C:/Program Files (x86)/REFPROP',
        'C:/Program Files/REFPROP'
    ]
    
    # 检查常用路径
    for path in common_paths:
        if path and os.path.exists(path):
            console.print(f"[OK] 找到REFPROP路径: [cyan]{path}[/]")
            return path
    
    console.print("[WARN] 未找到REFPROP路径，请输入REFPROP安装路径")
    while True:
        user_path = Prompt.ask("REFPROP安装路径").strip()
        if os.path.exists(user_path):
            console.print(f"[OK] 使用REFPROP路径: [cyan]{user_path}[/]")
            return user_path
        else:
            console.print("[ERR] 路径不存在，请重新输入！")


def get_user_input():
    """
    交互式获取用户输入参数，提供默认值说明。
    """
    console.print()
    console.print("=" * 60)
    console.print("            [bold cyan]RefEquiv[/] - [dim]制冷剂等效气相物性计算器[/]")
    console.print("=" * 60)
    console.print("\n[dim]提示：直接回车使用默认值[/]\n")

    # FLUID
    default_fluid = "R454C"
    fluid = Prompt.ask(
        "[bold]流体名称[/]",
        default=default_fluid
    )

    # PRESSURE_RANGE_MPa (无默认值)
    while True:
        pressure_input = Prompt.ask(
            "[bold]压力值（MPa，多个用空格分隔）[/]"
        )
        if pressure_input and pressure_input.strip():
            try:
                PRESSURE_RANGE_MPa = [float(p) for p in pressure_input.split()]
                break
            except ValueError:
                console.print("[red][WARN][/] 请输入有效的数值！")
        else:
            console.print("[red][WARN][/] 压力值不能为空！")

    # N_POINTS_PER_PRESSURE
    default_n_points = 50
    n_input = Prompt.ask(
        "[bold]每个压力的干度离散点数[/]",
        default=str(default_n_points)
    )
    N_POINTS_PER_PRESSURE = int(n_input)

    # VISCOSITY_MODEL
    console.print()
    console.print("[dim]选择粘度模型：[/]")
    console.print("  [cyan]1[/] - McAdams：调和平均，基于质量含气率Q，适用于常规两相流压降计算")
    console.print("  [cyan]2[/] - Cicchitti：体积加权算术平均，基于气相体积分数，适用于高流速均匀流动 [dim](推荐)[/]")
    default_vis = 'cicchitti'
    vis_input = Prompt.ask(
        "[bold]粘度模型[/]",
        choices=["1", "2"],
        default="2"
    )
    VISCOSITY_MODEL = 'mcadams' if vis_input == "1" else default_vis

    # CP_METHOD
    console.print()
    console.print("[dim]选择等效比热容方法：[/]")
    console.print("  [cyan]1[/] - weighted：质量加权平均 cp = (1-Q)·CP_LIQ + Q·CP_VAP")
    console.print("  [cyan]2[/] - enthalpy_based：基于焓差的等效比热容 [dim](推荐)[/]")
    console.print("  [cyan]3[/] - gas：直接使用饱和气比热容 CP_VAP [dim](不推荐，忽略温度滑移)[/]")
    default_cp = 'enthalpy_based'
    cp_input = Prompt.ask(
        "[bold]等效比热容方法[/]",
        choices=["1", "2", "3"],
        default="2"
    )
    if cp_input == "1":
        CP_METHOD = 'weighted'
    elif cp_input == "3":
        CP_METHOD = 'gas'
    else:
        CP_METHOD = default_cp

    # 配置确认
    console.print()
    console.print("[bold]配置确认[/]")
    console.print("-" * 40)
    console.print(f"  流体: [yellow]{fluid}[/]")
    console.print(f"  压力: [yellow]{', '.join([f'{p:.3f}' for p in PRESSURE_RANGE_MPa])} MPa[/]")
    console.print(f"  离散点数: [yellow]{N_POINTS_PER_PRESSURE}[/]")
    console.print(f"  粘度模型: [yellow]{VISCOSITY_MODEL}[/]")
    console.print(f"  比热容方法: [yellow]{CP_METHOD}[/]")
    console.print("-" * 40)
    console.print()

    return fluid, PRESSURE_RANGE_MPa, N_POINTS_PER_PRESSURE, VISCOSITY_MODEL, CP_METHOD


def main():
    """
    主程序：交互式配置参数并计算等效气相物性表。
    """
    # 获取用户输入
    FLUID, PRESSURE_RANGE_MPa, N_POINTS_PER_PRESSURE, VISCOSITY_MODEL, CP_METHOD = get_user_input()

    # 生成输出文件名，支持单个或多个压力值
    if len(PRESSURE_RANGE_MPa) == 1:
        OUTPUT_EXCEL_PATH = f"{FLUID}_{PRESSURE_RANGE_MPa[0]:.3f}MPa_等效气相物性表.xlsx"
    else:
        # 多个压力值时，用下划线连接
        pressure_str = "_".join([f"{p:.3f}" for p in PRESSURE_RANGE_MPa])
        OUTPUT_EXCEL_PATH = f"{FLUID}_{pressure_str}MPa_等效气相物性表.xlsx"
    
    # 获取并验证REFPROP路径
    REFPROP_PATH = get_refprop_path()
    
    console.print()
    console.print(Text.assemble(
        "初始化 ",
        ("REFPROP", "bold cyan"),
        ": ",
        (f"{REFPROP_PATH}", "dim")
    ))
    
    try:
        RP = REFPROPFunctionLibrary(REFPROP_PATH)
        RP.SETPATHdll(REFPROP_PATH)

        # 快速测试
        test_p = PRESSURE_RANGE_MPa[0] * 1e6
        T_test_b = get_single_prop(RP, FLUID, test_p, 0.0, "T") - 273.15
        T_test_d = get_single_prop(RP, FLUID, test_p, 1.0, "T") - 273.15
        
        ready_text = Text()
        ready_text.append("[OK] REFPROP ", style="green bold")
        ready_text.append("就绪 | ", style="green")
        ready_text.append(f"{FLUID}", style="cyan bold")
        ready_text.append(" @ ", style="dim")
        ready_text.append(f"{PRESSURE_RANGE_MPa[0]:.3f} MPa", style="yellow")
        ready_text.append(": 泡点 ", style="dim")
        ready_text.append(f"{T_test_b:.2f}℃", style="blue")
        ready_text.append(", 露点 ", style="dim")
        ready_text.append(f"{T_test_d:.2f}℃", style="blue")
        ready_text.append(", 滑移 ", style="dim")
        ready_text.append(f"{T_test_d - T_test_b:.2f}℃", style="cyan")
        console.print(ready_text)
        console.print()
    except Exception as e:
        console.print(Text.assemble(
            ("[ERR] REFPROP 初始化失败: ", "red bold"),
            (f"{e}", "red")
        ))
        return

    all_data = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        main_task = progress.add_task("计算物性数据...", total=len(PRESSURE_RANGE_MPa))
        
        for p in PRESSURE_RANGE_MPa:
            progress.update(main_task, description=f"计算压力: [yellow]{p:.3f}[/] MPa")
            
            try:
                df, T_bubble, T_dew = generate_single_pressure_table(
                    RP, FLUID, p, N_POINTS_PER_PRESSURE,
                    μ_model=VISCOSITY_MODEL,
                    cp_method=CP_METHOD
                )
                df.insert(0, '压力(MPa)', p)
                all_data.append(df)
                
                success_text = Text()
                success_text.append("  [OK] 压力 ", style="dim")
                success_text.append(f"{p:.3f} MPa", style="yellow")
                success_text.append(" 完成，有效点: ", style="dim")
                success_text.append(f"{len(df)}", style="green bold")
                console.print(success_text)
                console.print()
            except Exception as e:
                err_text = Text()
                err_text.append("  [ERR] 压力 ", style="dim")
                err_text.append(f"{p:.3f} MPa", style="yellow")
                err_text.append(" 失败: ", style="red")
                err_text.append(f"{e}", style="red dim")
                console.print(err_text)
                console.print()
            
            progress.advance(main_task)

    if not all_data:
        console.print("[red]无数据可输出。[/]")
        return

    final_df = pd.concat(all_data, ignore_index=True)

    console.print(Text.assemble(
        "写入 ",
        ("Excel", "bold green"),
        ": ",
        (f"{OUTPUT_EXCEL_PATH}", "cyan")
    ))
    
    with pd.ExcelWriter(OUTPUT_EXCEL_PATH, engine='openpyxl', mode='w') as writer:
        unique_pressures = list(dict.fromkeys(PRESSURE_RANGE_MPa))
        for p in unique_pressures:
            sub = final_df[final_df['压力(MPa)'] == p].drop(columns=['压力(MPa)'])
            sub.to_excel(writer, sheet_name=f'{p}MPa', index=False)

    console.print()
    console.print("=" * 60)
    console.print(
        Text.assemble(
            ("[OK] 完成！", "bold green"),
            " 共 ",
            (f"{len(PRESSURE_RANGE_MPa)}", "cyan bold"),
            " 个压力，",
            (f"{len(final_df)}", "cyan bold"),
            " 行数据"
        )
    )
    console.print("=" * 60)

    # 预览
    console.print()
    for p in unique_pressures:
        pdata = final_df[final_df['压力(MPa)'] == p]
        
        preview_title = Text()
        preview_title.append("-> ", style="cyan")
        preview_title.append(f"{p} MPa", style="yellow bold")
        preview_title.append(" 结果预览", style="dim")
        preview_title.append(f" (等效比热容方法: {CP_METHOD})", style="dim")
        
        console.print(preview_title)
        
        # 显示预览数据（不用table）
        preview_data = pdata[['温度(℃)', '干度Q', '等效比热容(J/kg-K)',
                            '等效导热率(W/m-K)', '等效动力粘度(Pa-s)']].head(5)
        
        for _, row in preview_data.iterrows():
            line = Text()
            line.append("  ", style="dim")
            line.append(f"温度={row['温度(℃)']:.2f}℃", style="blue")
            line.append(" | ", style="dim")
            line.append(f"Q={row['干度Q']:.3f}", style="cyan")
            line.append(" | ", style="dim")
            line.append(f"cp={row['等效比热容(J/kg-K)']:.2f}", style="green")
            line.append(" | ", style="dim")
            line.append(f"λ={row['等效导热率(W/m-K)']:.6f}", style="magenta")
            line.append(" | ", style="dim")
            line.append(f"μ={row['等效动力粘度(Pa-s)']:.2e}", style="yellow")
            console.print(line)
        
        console.print("  ...", style="dim")
        console.print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/]")
    except Exception as e:
        console.print(f"\n[red]程序出错:[/] {e}")
    finally:
        console.print()
        console.print("=" * 60)
        Prompt.ask("[dim]按回车键退出[/]")