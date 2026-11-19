import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';

/// 持久化服务统一入口。
///
/// - [PrefsService]：SharedPreferences 键值存储，io / web 通用，直接在此定义；
/// - [FileStorage] / [DatabaseService]：平台相关（桌面=文件+SQLite，Web=下载+localStorage），
///   通过条件导出选择实现。
export 'storage_io.dart' if (dart.library.html) 'storage_web.dart';

/// 轻量级键值对持久化：保存用户偏好设置（SharedPreferences 同时支持 io / web）。
class PrefsService {
  PrefsService._();

  static Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  // 预算档位 low/mid/high
  static Future<void> saveBudgetLevel(String v) async =>
      (await _prefs).setString(AppConfig.prefsBudgetLevel, v);

  static Future<String> loadBudgetLevel() async =>
      (await _prefs).getString(AppConfig.prefsBudgetLevel) ?? 'mid';

  // 默认出发城市
  static Future<void> saveDefaultDeparture(String v) async =>
      (await _prefs).setString(AppConfig.prefsDefaultDeparture, v);

  static Future<String> loadDefaultDeparture() async =>
      (await _prefs).getString(AppConfig.prefsDefaultDeparture) ?? '北京';

  // 口味：嗜辣 / 清淡
  static Future<void> savePreferSpicy(bool v) async =>
      (await _prefs).setBool(AppConfig.prefsSpicy, v);

  static Future<bool> loadPreferSpicy() async =>
      (await _prefs).getBool(AppConfig.prefsSpicy) ?? false;

  static Future<void> savePreferLight(bool v) async =>
      (await _prefs).setBool(AppConfig.prefsLight, v);

  static Future<bool> loadPreferLight() async =>
      (await _prefs).getBool(AppConfig.prefsLight) ?? false;

  // AI 增强开关
  static Future<void> saveAiEnabled(bool v) async =>
      (await _prefs).setBool(AppConfig.prefsAiEnabled, v);

  static Future<bool> loadAiEnabled() async =>
      (await _prefs).getBool(AppConfig.prefsAiEnabled) ?? true;

  // ===================== 个人信息 =====================

  // 大概住址
  static Future<void> saveAddress(String v) async =>
      (await _prefs).setString(AppConfig.prefsAddress, v);

  static Future<String> loadAddress() async =>
      (await _prefs).getString(AppConfig.prefsAddress) ?? '';

  // 口味：甜口
  static Future<void> savePreferSweet(bool v) async =>
      (await _prefs).setBool(AppConfig.prefsPreferSweet, v);

  static Future<bool> loadPreferSweet() async =>
      (await _prefs).getBool(AppConfig.prefsPreferSweet) ?? false;

  // 景点偏好标签（多选）
  static Future<void> saveAttractionPref(List<String> v) async =>
      (await _prefs).setStringList(AppConfig.prefsAttractionPref, v);

  static Future<List<String>> loadAttractionPref() async =>
      (await _prefs).getStringList(AppConfig.prefsAttractionPref) ?? const [];

  // 旅行风格 fast/slow
  static Future<void> saveTravelStyle(String v) async =>
      (await _prefs).setString(AppConfig.prefsTravelStyle, v);

  static Future<String> loadTravelStyle() async =>
      (await _prefs).getString(AppConfig.prefsTravelStyle) ?? 'fast';

  // 住宿预算（元）
  static Future<void> saveAccommodationBudget(int v) async =>
      (await _prefs).setInt(AppConfig.prefsAccommodationBudget, v);

  static Future<int> loadAccommodationBudget() async =>
      (await _prefs).getInt(AppConfig.prefsAccommodationBudget) ?? 0;

  // 出行预算（元）
  static Future<void> saveTransportBudget(int v) async =>
      (await _prefs).setInt(AppConfig.prefsTransportBudget, v);

  static Future<int> loadTransportBudget() async =>
      (await _prefs).getInt(AppConfig.prefsTransportBudget) ?? 0;

  // 总预算上限（元）
  static Future<void> saveTotalBudget(int v) async =>
      (await _prefs).setInt(AppConfig.prefsTotalBudget, v);

  static Future<int> loadTotalBudget() async =>
      (await _prefs).getInt(AppConfig.prefsTotalBudget) ?? 0;

  // ===================== 口味偏好（多选） =====================

  static Future<void> saveTastes(List<String> v) async =>
      (await _prefs).setStringList(AppConfig.prefsTastes, v);

  /// 读口味偏好；为空时回退旧「辣/清/甜」三个开关做一次迁移。
  static Future<List<String>> loadTastes() async {
    final p = await _prefs;
    final list = p.getStringList(AppConfig.prefsTastes);
    if (list != null && list.isNotEmpty) return list;
    final out = <String>[];
    if (p.getBool(AppConfig.prefsSpicy) ?? false) out.add('spicy');
    if (p.getBool(AppConfig.prefsLight) ?? false) out.add('light');
    if (p.getBool(AppConfig.prefsPreferSweet) ?? false) out.add('sweet');
    return out;
  }

  // ===================== 首次引导 =====================

  static Future<void> saveOnboarded(bool v) async =>
      (await _prefs).setBool(AppConfig.prefsOnboarded, v);

  static Future<bool> loadOnboarded() async =>
      (await _prefs).getBool(AppConfig.prefsOnboarded) ?? false;

  /// 是否已填写过个人信息（住址 / 景点偏好 / 三档预算 / 口味 任一非空即视为已填）。
  static Future<bool> hasPersonalInfo() async {
    if ((await loadAddress()).isNotEmpty) return true;
    if ((await loadAttractionPref()).isNotEmpty) return true;
    if ((await loadAccommodationBudget()) > 0) return true;
    if ((await loadTransportBudget()) > 0) return true;
    if ((await loadTotalBudget()) > 0) return true;
    if ((await loadTastes()).isNotEmpty) return true;
    return false;
  }

  /// 一键清理个人信息：清空住址/口味/景点偏好/旅行风格/三档预算，并重置首次引导。
  static Future<void> clearPersonalInfo() async {
    final p = await _prefs;
    await p.remove(AppConfig.prefsAddress);
    await p.remove(AppConfig.prefsTastes);
    await p.remove(AppConfig.prefsAttractionPref);
    await p.remove(AppConfig.prefsTravelStyle);
    await p.remove(AppConfig.prefsAccommodationBudget);
    await p.remove(AppConfig.prefsTransportBudget);
    await p.remove(AppConfig.prefsTotalBudget);
    await p.setBool(AppConfig.prefsOnboarded, false);
  }

  static Future<void> clearAll() async => (await _prefs).clear();
}
