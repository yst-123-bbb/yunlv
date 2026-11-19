// Web 端专属文件（仅被 `if (dart.library.html)` 条件导入），
// 用 dart:html 实现浏览器下载，属预期的 Web-only 用法，故关闭相关提示。
// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:convert';
import 'dart:html' as html;

import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';
import 'plan_text.dart';

/// Web（浏览器）端的持久化实现。
///
/// 该文件仅在 Web 平台被条件导入（见 storage_service.dart 的 `export ... if`）。
/// 桌面 / 移动端由 storage_io.dart 提供同名实现。
/// 说明：Web 无真实文件系统与原生 SQLite，因此：
///  - 文件导出 → 触发浏览器下载（Blob）；
///  - 历史 → 使用 SharedPreferences（localStorage）以 JSON 数组持久化。

// ==================== 文件导出（浏览器下载） ====================

/// 浏览器下载实现行程单导出（.txt / .json）。
class FileStorage {
  FileStorage._();

  static String _stamp() {
    final n = DateTime.now();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${n.year}${two(n.month)}${two(n.day)}_${two(n.hour)}${two(n.minute)}${two(n.second)}';
  }

  static Future<String> exportPlanText(Plan plan, String city) async {
    return _download('行程单_${city}_${_stamp()}.txt', buildPlanText(plan, city));
  }

  static Future<String> exportPlanJson(Plan plan, String city) async {
    final payload = {'city': city, 'plan': plan.toJson(), 'exported_at': DateTime.now().toString()};
    return _download('行程单_${city}_${_stamp()}.json', const JsonEncoder.withIndent('  ').convert(payload));
  }

  /// 触发浏览器下载，返回提示文案（Web 端无绝对路径）。
  static Future<String> _download(String filename, String content) async {
    final bytes = utf8.encode(content);
    final blob = html.Blob([bytes], 'text/plain;charset=utf-8');
    final url = html.Url.createObjectUrlFromBlob(blob);
    final anchor = html.AnchorElement(href: url)
      ..setAttribute('download', filename)
      ..style.display = 'none';
    html.document.body?.children.add(anchor);
    anchor.click();
    anchor.remove();
    html.Url.revokeObjectUrl(url);
    return '已通过浏览器下载：$filename';
  }
}

// ==================== 历史（localStorage） ====================

/// 结构化数据持久化：历史行程（CRUD），基于 SharedPreferences 的 JSON 数组。
class DatabaseService {
  DatabaseService._();

  static const String _historyKey = 'yunlv_history';

  static Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  static int _nextId(List<Map<String, dynamic>> list) {
    var max = 0;
    for (final e in list) {
      final id = (e['id'] as num?)?.toInt() ?? 0;
      if (id > max) max = id;
    }
    return max + 1;
  }

  static List<Map<String, dynamic>> _decode(String? raw) {
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list.map((e) => (e as Map).map((k, v) => MapEntry(k.toString(), v))).toList();
    } catch (_) {
      return [];
    }
  }

  // ---------- 历史行程 ----------

  static Future<int> addHistory({
    required String city,
    required int days,
    required String styleName,
    required String recommendation,
    required String planJson,
  }) async {
    final prefs = await _prefs;
    final list = _decode(prefs.getString(_historyKey));
    final id = _nextId(list);
    list.add({
      'id': id,
      'city': city,
      'days': days,
      'style_name': styleName,
      'recommendation': recommendation,
      'plan_json': planJson,
      'created_at': DateTime.now().toString(),
    });
    await prefs.setString(_historyKey, jsonEncode(list));
    return id;
  }

  /// 更新一条历史行程（编辑方案后回写，避免重复新增）。
  static Future<int> updateHistory({
    required int id,
    required String city,
    required int days,
    required String styleName,
    required String recommendation,
    required String planJson,
  }) async {
    final prefs = await _prefs;
    final list = _decode(prefs.getString(_historyKey));
    for (var i = 0; i < list.length; i++) {
      if ((list[i]['id'] as num?)?.toInt() == id) {
        list[i] = {
          'id': id,
          'city': city,
          'days': days,
          'style_name': styleName,
          'recommendation': recommendation,
          'plan_json': planJson,
          'created_at': DateTime.now().toString(),
        };
        break;
      }
    }
    await prefs.setString(_historyKey, jsonEncode(list));
    return 1;
  }

  static Future<List<Map<String, dynamic>>> queryHistory() async {
    final prefs = await _prefs;
    return _decode(prefs.getString(_historyKey)).reversed.toList();
  }

  static Future<int> deleteHistory(int id) async {
    final prefs = await _prefs;
    final list = _decode(prefs.getString(_historyKey))..removeWhere((e) => (e['id'] as num?)?.toInt() == id);
    await prefs.setString(_historyKey, jsonEncode(list));
    return 1;
  }

  static Future<int> clearHistory() async {
    final prefs = await _prefs;
    await prefs.setString(_historyKey, '[]');
    return 1;
  }
}
