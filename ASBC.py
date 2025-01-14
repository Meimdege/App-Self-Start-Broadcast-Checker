import subprocess
import time
import re


def run_adb_command(command):
    """运行ADB命令并返回输出结果"""
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"运行命令时出错: {command}\n{result.stderr}")
        return None
    return result.stdout

def run_as_root(command):
    """使用su权限运行命令"""
    try:
        full_command = f'adb shell "su -c \'{command}\'"'
        result = subprocess.run(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"运行root命令时出错: {command}\n{result.stderr}")
            return None
        return result.stdout
    except Exception as e:
        print(f"运行root命令时发生异常: {e}")
        return None

def send_broadcast_as_root(action, package_name):
    """以root权限发送广播"""
    command = f"am broadcast -a {action} -p {package_name}"
    return run_as_root(command)

def get_running_processes():
    """获取当前正在运行的进程列表"""
    processes_output = run_as_root("ps")
    if not processes_output:
        return []

    # 从输出中提取进程名
    processes = [line.split()[-1] for line in processes_output.strip().split("\n")[1:]]
    return processes

def get_app_broadcasts(package_name):
    """获取应用支持的广播动作"""
    dumpsys_output = run_adb_command(f"adb shell dumpsys package {package_name}")
    if not dumpsys_output:
        return []

    # 使用正则表达式提取广播动作
    actions = re.findall(r'Action: \"(.*?)\"', dumpsys_output)
    if not actions:
        print("未找到广播动作。")
    return actions

def get_common_broadcasts():
    """返回常见的Android广播动作"""
    return [
        "android.intent.action.BOOT_COMPLETED",
        "android.intent.action.LOCKED_BOOT_COMPLETED",
        "android.intent.action.PRE_BOOT_COMPLETED",
        "android.intent.action.PHONE_STATE",
        "android.intent.action.SCREEN_ON",
        "android.intent.action.SCREEN_OFF",
        "android.intent.action.USER_PRESENT",
        "android.intent.action.ACTION_POWER_CONNECTED",
        "android.intent.action.ACTION_POWER_DISCONNECTED",
        "android.intent.action.AIRPLANE_MODE",
        "android.intent.action.LOW_BATTERY",
        "android.intent.action.TIME_SET",
        "android.intent.action.DATE_CHANGED",
        "android.intent.action.LOCALE_CHANGED",
        "android.intent.action.DEVICE_STORAGE_LOW",
        "android.intent.action.DEVICE_STORAGE_OK",
        "android.net.conn.CONNECTIVITY_CHANGE",
    ]

def get_vendor_broadcasts():
    """返回厂商特定的广播动作"""
    return [
        # 小米
        "miui.intent.action.BOOT_COMPLETED",
        "com.miui.securitycenter.BOOT_COMPLETED",
        "com.miui.intent.action.ALARM_WAKEUP",

        # 华为
        "huawei.intent.action.BOOT_COMPLETED",
        "huawei.intent.action.POWER_CONNECTED",

        # OPPO
        "oppo.intent.action.BOOT_COMPLETED"
    ]

def kill_process(process_name):
    """通过进程名杀死指定进程"""
    try:
        # 先获取所有进程信息
        command = f'adb shell "pgrep -f {process_name}"'  # 使用pgrep找到进程ID
        process_output = run_adb_command(command)
        print(f"进程输出: {process_output}")
        
        if process_output:
            # 将输出的进程ID按行拆分并杀死每个进程
            pid_list = process_output.strip().split('\n')
            for pid in pid_list:
                kill_command = f'adb shell su -c "kill {pid}"'
                run_adb_command(kill_command)
                print(f"已杀死进程 {process_name}，PID: {pid}")
        else:
            print(f"未找到运行的进程: {process_name}")
    
    except Exception as e:
        print(f"杀死进程 {process_name} 时发生异常: {e}")

def monitor_auto_start(package_name, action):
    """监控应用在接收到广播后是否启动了进程或记录了活动"""
    print(f"监控自动启动: 包名: {package_name}, 广播动作: {action}")

    # 步骤1: 获取初始进程列表
    initial_processes = set(get_running_processes())

    # 步骤2: 检查目标进程是否在运行并杀死它
    if any(package_name in process for process in initial_processes):
        print(f"发现目标进程 {package_name}，正在杀死...")
        kill_process(package_name)

    # 步骤3: 发送广播
    send_broadcast_as_root(action, package_name)

    # 步骤4: 获取更新后的进程列表
    updated_processes = set(get_running_processes())

        # 步骤5: 检查是否有新进程启动
    new_processes = updated_processes - initial_processes
    # 过滤出包含输入包名的进程
    filtered_processes = [process for process in new_processes if package_name in process]
    process_result = any(package_name in process for process in new_processes)

    if process_result:
        print(f"包 {package_name} 启动了新进程: {filtered_processes}")
    else:
        print(f"未检测到包 {package_name} 的新进程。")


    return process_result


def main():
    package_name = input("请输入要监控的包名（不能为空）: ").strip()
    if not package_name:
        print("错误: 必须输入包名！")
        return

    # 部分应用的广播会导致无限循环启动，如：com.miui.securitycenter.BOOT_COMPLETED，影响程序正常运行，故需要排除掉这些广播包
    Noactions = ["com.android.launcher.action.INSTALL_SHORTCUT", "com.miui.securitycenter.BOOT_COMPLETED"]

    # 步骤1: 获取常见广播动作
    actions = get_common_broadcasts()
    actions.extend(get_vendor_broadcasts())
    actions.extend(get_app_broadcasts(package_name))
    actions = list(filter(lambda x: x not in Noactions, actions))

    print("正在发送广播动作并监控自动启动响应...")

    # 步骤2: 为每个广播动作监控响应
    for action in actions:
        print(f"\n--- 测试广播: {action} ---")
        result = monitor_auto_start(package_name, action)
        if result:
            print(f"【XXXXX】检测到包 {package_name} 在广播动作 {action} 下自动启动")
        else:
            print(f"未检测到包 {package_name} 在广播动作 {action} 下自动启动")

if __name__ == "__main__":
    main()
