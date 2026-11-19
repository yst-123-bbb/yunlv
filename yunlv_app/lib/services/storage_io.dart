import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
// sqflite 以依赖方式引入；此处通过 sqflite_common_ffi 复用同一套 sqflite_common API。
// 桌面端用 FFI 实现，移动端也由 sqlite3_flutter_libs 打包的原生库承载，跨平台统一。
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import '../models/models.dart';
import 'plan_text.dart';

/// 桌面 / 移动端的持久化实现（dart:io + SQLite）。
///
/// 该文件仅在非 Web 平台被条件导入（见 storage_service.dart 的 `export ... if`），
/// Web 端由 storage_web.dart 提供同名实现。

// ==================== 文件 IO（行程导出） ====================

/// 基于 dart:io File 实现行程单导出（.txt / .json）。
class FileStorage {
  FileStorage._();

  /// 获取应用文档目录（失败回退系统临时目录，避免 MissingPluginException）
  static Future<Directory> _dir() async {
    try {
      return await getApplicationDocumentsDirectory();
    } catch (_) {
      return Directory.systemTemp;
    }
  }

  static String _stamp() {
    final n = DateTime.now();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${n.year}${two(n.month)}${two(n.day)}_${two(n.hour)}${two(n.minute)}${two(n.second)}';
  }

  /// 将行程方案导出为 .txt 文本文件，返回写入后的绝对路径。
  static Future<String> exportPlanText(Plan plan, String city) async {
    final dir = await _dir();
    final file = File('${dir.path}${Platform.pathSeparator}行程单_${city}_${_stamp()}.txt');
    await file.writeAsString(buildPlanText(plan, city));
    return file.path;
  }

  /// 将行程方案导出为 .json 结构化文件，返回写入后的绝对路径。
  static Future<String> exportPlanJson(Plan plan, String city) async {
    final dir = await _dir();
    final file = File('${dir.path}${Platform.pathSeparator}行程单_${city}_${_stamp()}.json');
    final payload = {'city': city, 'plan': plan.toJson(), 'exported_at': DateTime.now().toString()};
    await file.writeAsString(const JsonEncoder.withIndent('  ').convert(payload));
    return file.path;
  }
}

// ==================== SQLite 数据库存储（历史） ====================

/// 结构化数据持久化：历史行程（CRUD）。
class DatabaseService {
  DatabaseService._();

  static const String _dbName = 'yunlv.db';
  static const int _dbVersion = 2;
  static const String _historyTable = 'history';

  static Database? _db;

  static Future<Directory> _dir() async {
    try {
      return await getApplicationDocumentsDirectory();
    } catch (_) {
      return Directory.systemTemp;
    }
  }

  /// 打开/创建数据库（懒加载单例），首次建表。
  static Future<Database> _database() async {
    if (_db != null) return _db!;
    // 桌面端必须显式初始化 FFI 实现并指定数据库工厂，否则 openDatabase 抛
    // 「databaseFactory not initialized」。web 端走 storage_web.dart，不经过此处。
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
    final dir = await _dir();
    final path = '${dir.path}${Platform.pathSeparator}$_dbName';
    _db = await openDatabase(
      path,
      version: _dbVersion,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE $_historyTable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            days INTEGER NOT NULL,
            style_name TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
          )
        ''');
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        // v1 -> v2：历史表用「推荐语」替代「评分」，重建历史表。
        if (oldVersion < 2) {
          await db.execute('DROP TABLE IF EXISTS $_historyTable');
          await db.execute('''
            CREATE TABLE $_historyTable (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              city TEXT NOT NULL,
              days INTEGER NOT NULL,
              style_name TEXT NOT NULL,
              recommendation TEXT NOT NULL,
              plan_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
          ''');
        }
      },
    );
    return _db!;
  }

  // ---------- 历史行程 ----------

  static Future<int> addHistory({
    required String city,
    required int days,
    required String styleName,
    required String recommendation,
    required String planJson,
  }) async {
    final db = await _database();
    return db.insert(_historyTable, {
      'city': city,
      'days': days,
      'style_name': styleName,
      'recommendation': recommendation,
      'plan_json': planJson,
      'created_at': DateTime.now().toString(),
    });
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
    final db = await _database();
    return db.update(
      _historyTable,
      {
        'city': city,
        'days': days,
        'style_name': styleName,
        'recommendation': recommendation,
        'plan_json': planJson,
        'created_at': DateTime.now().toString(),
      },
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  static Future<List<Map<String, dynamic>>> queryHistory() async {
    final db = await _database();
    return db.query(_historyTable, orderBy: 'id DESC');
  }

  static Future<int> deleteHistory(int id) async {
    final db = await _database();
    return db.delete(_historyTable, where: 'id = ?', whereArgs: [id]);
  }

  static Future<int> clearHistory() async {
    final db = await _database();
    return db.delete(_historyTable);
  }
}
