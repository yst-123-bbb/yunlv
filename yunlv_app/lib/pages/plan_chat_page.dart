import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../services/data_repository.dart';
import '../services/deepseek_service.dart';
import '../services/plan_generator.dart';
import '../services/storage_service.dart';
import '../services/transit_service.dart';
import '../services/waypoints.dart';

/// AI 行程定制页：通过对话收集出行需求，识别后调用本地规则引擎生成方案。
///
/// 用户在首页选好的「行程站点 / 途经地 / 个人信息」会通过 [seedCities]/[seedWaypoints]
/// 同步进来；用户用自然语言补充（出发地 / 目的地 / 天数 / 人数 / 预算 / 游玩时间），
/// 本页本地解析出结构化需求，生成多风格方案并跳转查看；识别不完整时交给 DeepSeek 追问。
/// 右上角「手动填写」可进入表单页补充（跨城班次选择等）。
class PlanChatPage extends StatefulWidget {
  final List<String> seedCities; // 首页已选行程站点（多目的地）
  final List<Waypoint> seedWaypoints; // 首页已选途经地（优先编排的景点）
  const PlanChatPage({
    super.key,
    this.seedCities = const [],
    this.seedWaypoints = const [],
  });

  @override
  State<PlanChatPage> createState() => _PlanChatPageState();
}

/// 本地解析出的出行需求（record）。
typedef _Req = ({String departure, List<String> cities, int days, int people, int budget});

class _PlanChatPageState extends State<PlanChatPage> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final List<ChatMessage> _messages = [];
  String _context = '';
  bool _loading = false;

  // 已生成方案（用于展示「查看行程」卡片）
  TripPreference? _pref;
  List<Plan> _plans = [];

  // 用户指定的总游玩天数（0=未指定，回退按景点时长自动估算）
  int _days = 0;

  // 用户选定的方案风格（默认经典打卡）
  String _styleId = 'classic';

  // 已询问「是否生成行程」，等待用户确认
  bool _awaitingConfirm = false;

  // 已给出「攻略预览 + 多方案」，等待用户选择方案风格
  bool _awaitingStyle = false;

  // 空闲时推荐的补充景点（用户同意后加入已选）
  List<Waypoint> _pendingRecs = [];

  // 已询问「是否添加推荐景点」，等待用户确认
  bool _awaitingRecs = false;

  // 待生成的需求（用户确认后据此生成）
  _Req? _pendingReq;

  // 已自动保存到「我的行程」的历史 id（详情页据此回写，避免重复新增）
  int? _savedHistoryId;

  // 跨城交通班次（对话中确认后记录，生成时并入方案）
  List<TransitLeg> _legs = [];

  // 已询问「班次确认」，等待用户确认/调整
  bool _awaitingLegs = false;

  // 本次规划的用户选择景点（初始 = 首页途经地；推荐景点选择后会更新）
  late List<Waypoint> _selected;

  static const List<String> _quickPrompts = [
    '从北京出发去上海和杭州玩5天，2个人，人均预算2000',
    '去成都玩3天，想吃火锅',
    '从广州出发去昆明玩4天，1个人',
  ];

  @override
  void initState() {
    super.initState();
    _selected = List.of(widget.seedWaypoints);
    _context = _buildContext();
    _messages.add(ChatMessage(role: 'assistant', content: _greeting()));
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// 开场白：同步展示首页已选内容，并引导补充（含游玩时间）。
  String _greeting() {
    final buf = StringBuffer('你好，我是云旅行程规划师 🤖\n');
    if (widget.seedCities.isNotEmpty) {
      buf.writeln('已读取你在首页选择的行程站点：${widget.seedCities.join('、')}。');
    }
    if (_selected.isNotEmpty) {
      final hours = _selected.fold<double>(0, (s, w) => s + w.attraction.playHours);
      buf.writeln('已读取 ${_selected.length} 个途经景点（预计游玩约 ${_fmtHours(hours)}）：'
          '${_selected.map((w) => w.attraction.name).join('、')}。');
      buf.writeln('请告诉我你的游玩时间，例如「玩 3 天」或「18 小时」，我会帮你判断时间是否够用。');
    } else if (widget.seedCities.isNotEmpty) {
      buf.writeln('你还没有选择具体景点。点下方「开始生成」或回复「推荐景点」，'
          '我会先推荐 ${widget.seedCities.join('、')} 的热门景点，让你挑选后生成方案。');
    } else {
      buf.writeln('用一句话告诉我你的出行计划（出发地、目的地、天数、人数、预算），我就帮你生成方案。');
    }
    buf.write('也可以点下方示例快速开始。');
    return buf.toString();
  }

  String _buildContext() {
    final repo = DataRepository.instance;
    final buf = StringBuffer();
    for (final c in repo.cities) {
      final attrs = repo.attractionsOf(c.name);
      if (attrs.isEmpty) continue;
      buf.writeln('${c.name}（${c.province}）：${attrs.take(5).map((a) => a.name).join('、')}');
    }
    return buf.toString();
  }

  /// 从自然语言中解析出行需求；缺少目的地时返回 null（交由 AI 追问）。
  _Req? _parseRequest(String text) {
    final repo = DataRepository.instance;
    final names = repo.cityNames.toList()..sort((a, b) => b.length.compareTo(a.length));
    final mentioned = names.where((c) => text.contains(c)).toList();

    String? departure;
    final mFrom = RegExp(r'从([一-龥]{2,8}?)(?:出发|去)').firstMatch(text);
    if (mFrom != null) {
      final raw = mFrom.group(1)!;
      for (final c in names) {
        if (raw.contains(c) || c.contains(raw)) {
          departure = c;
          break;
        }
      }
    } else if (mentioned.isNotEmpty && text.contains('从')) {
      departure = mentioned.first;
    }

    final destinations = mentioned.where((c) => c != departure).toList();
    if (destinations.isEmpty) return null;

    int num(RegExp r) => int.tryParse(r.firstMatch(text)?.group(1) ?? '') ?? 0;
    return (
      departure: departure ?? '',
      cities: destinations,
      days: num(RegExp(r'(\d+)\s*天')),
      people: num(RegExp(r'(\d+)\s*人')),
      budget: num(RegExp(r'(\d+)\s*元')),
    );
  }

  /// 解析游玩时间（小时）：支持「X 天」或「X 小时」。
  int? _parseDuration(String text) {
    final mDay = RegExp(r'(\d+(?:\.\d+)?)\s*天').firstMatch(text);
    if (mDay != null) return (double.parse(mDay.group(1)!) * hoursPerDay).round();
    final mHour = RegExp(r'(\d+(?:\.\d+)?)\s*小时').firstMatch(text);
    if (mHour != null) return double.parse(mHour.group(1)!).round();
    return null;
  }

  /// 解析用户说的游玩天数（「X 天」→ X），未提到返回 null。
  int? _parseDays(String text) {
    final m = RegExp(r'(\d+(?:\.\d+)?)\s*天').firstMatch(text);
    if (m == null) return null;
    final d = double.parse(m.group(1)!);
    return d < 1 ? 1 : d.round();
  }

  /// 是否「生成」类指令（用于已选站点/途经地时直接出方案）。
  bool _isGenerateCommand(String text) =>
      RegExp(r'生成|规划|开始|出发|走吧|好|可以|行|确认|就这样|ok|go|plan|推荐', caseSensitive: false)
          .hasMatch(text);

  String _today() {
    final n = DateTime.now();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${n.year}-${two(n.month)}-${two(n.day)}';
  }

  Future<void> _send(String text) async {
    final q = text.trim();
    if (q.isEmpty || _loading) return;
    setState(() => _messages.add(ChatMessage(role: 'user', content: q)));
    _input.clear();
    _scrollToBottom();

    // 0. 已询问「是否生成」：用户表态是否确认
    if (_awaitingConfirm) {
      _awaitingConfirm = false;
      if (_isGenerateCommand(q)) {
        await _generateConfirmed();
        return;
      }
      // 未确认（想继续补充）：落到后续解析
    }

    // 0.5 已询问「班次确认」：用户确认 / 调整班次
    if (_awaitingLegs) {
      _awaitingLegs = false;
      if (await _handleLegsReply(q)) return;
      // 未识别：落到后续解析
    }

    // 0.6 已询问「是否添加推荐景点」：用户确认添加 / 跳过
    if (_awaitingRecs) {
      _awaitingRecs = false;
      if (await _handleRecsReply(q)) return;
      // 未识别：落到后续解析
    }

    // 0.7 已给出「攻略预览 + 多方案」，等待用户选择方案风格
    if (_awaitingStyle) {
      _awaitingStyle = false;
      if (await _handleStyleReply(q)) return;
      // 未识别：落到后续解析
    }

    // 1. 解析出目的地（含天数）→ 记录天数并给出攻略预览 + 多方案
    final req = _parseRequest(q);
    if (req != null && req.cities.isNotEmpty) {
      await _onDestination(req);
      return;
    }

    // 2. 已有途经景点但未定天数：优先解析「X 天」，其次「X 小时」游玩时长
    if (_selected.isNotEmpty && _days == 0) {
      final daysFromText = _parseDays(q);
      if (daysFromText != null) {
        _days = daysFromText;
        await _showRoughPlans(null);
        return;
      }
      final dur = _parseDuration(q);
      if (dur != null) {
        await _answerPlayTime(dur);
        return;
      }
    }

    // 3. 只选了城市、没选景点，且是「推荐/生成」类指令 → 先推荐热门景点让用户挑选
    if (widget.seedCities.isNotEmpty && _selected.isEmpty && _isGenerateCommand(q)) {
      setState(() => _loading = true);
      await _recommendAndPickAttractions();
      if (!mounted) return;
      setState(() => _loading = false);
      _scrollToBottom();
      return;
    }

    // 4. 基于首页已选内容 + 生成类指令 → 给攻略预览 + 多方案
    if ((widget.seedCities.isNotEmpty || _selected.isNotEmpty) &&
        _isGenerateCommand(q)) {
      await _showRoughPlans(null);
      return;
    }

    // 5. 未识别：DeepSeek 追问，失败回退本地提示
    setState(() => _loading = true);
    final reply = await DeepSeekService.chat(List.of(_messages), context: _context);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _messages.add(ChatMessage(
        role: 'assistant',
        content: reply ?? '我还不知道你想去哪里呢～请告诉我目的地城市，例如「从北京出发去杭州玩3天」。',
      ));
    });
    _scrollToBottom();
  }

  /// 校验游玩时间：超时建议增时/减点，空闲则推荐景点并询问是否添加；
  /// 时间充足或刚好时，把小时换算成天数，进入攻略预览 + 多方案选择。
  Future<void> _answerPlayTime(int availableHours) async {
    final total = _selected.fold<double>(0, (s, w) => s + w.attraction.playHours);
    setState(() {
      _messages.add(ChatMessage(
        role: 'assistant',
        content: _playTimeSuggestion(total, availableHours),
      ));
    });
    _scrollToBottom();
    if (total <= availableHours) {
      final d = (availableHours / hoursPerDay).ceil();
      _days = d < 1 ? 1 : (d > 7 ? 7 : d);
      // 有空闲时间：推荐补充景点并询问是否添加；刚好则直接进攻略
      if (total < availableHours) {
        await _promptAddRecommendations(availableHours - total);
        return;
      }
      await _showRoughPlans(null);
    }
  }

  String _playTimeSuggestion(double totalHours, int availableHours) {
    final needDays = (totalHours / hoursPerDay).ceil();
    if (totalHours > availableHours) {
      return '你选的 ${_selected.length} 个景点预计需要约 ${_fmtHours(totalHours)}（$needDays 天），'
          '超过了你的 ${_fmtHours(availableHours.toDouble())}。\n'
          '建议：① 把游玩时间增加到 $needDays 天；② 或减少景点（在首页「途经地」移除部分景点后重新开始）。';
    }
    if (totalHours < availableHours) {
      final free = availableHours - totalHours;
      return '你的游玩时间充足：${_fmtHours(availableHours.toDouble())} 内还剩余约 ${_fmtHours(free.toDouble())}。'
          '我这就为你推荐几个补充景点。';
    }
    return '刚好合适！景点约 ${_fmtHours(totalHours)}，与你 ${_fmtHours(availableHours.toDouble())} 的游玩时间吻合。'
        '接下来我会给你一份攻略预览，并让你选择方案风格。';
  }

  /// 从站点/途经地所在城市里挑热门景点，尽量填满空闲时间。
  List<Waypoint> _recommendToFill(double freeHours) {
    final repo = DataRepository.instance;
    final citySet = <String>{...widget.seedCities};
    for (final w in _selected) {
      citySet.add(w.city);
    }
    final selected = _selected.map((w) => w.attraction.name).toSet();

    final candidates = <Waypoint>[];
    for (final c in citySet) {
      for (final a in repo.attractionsOf(c)) {
        if (selected.contains(a.name)) continue;
        candidates.add(Waypoint(city: c, attraction: a));
      }
    }
    candidates.sort((a, b) => b.attraction.likes.compareTo(a.attraction.likes));

    final out = <Waypoint>[];
    var acc = 0.0;
    for (final w in candidates) {
      if (acc >= freeHours) break;
      out.add(w);
      acc += w.attraction.playHours;
      if (out.length >= 4) break;
    }
    return out;
  }

  /// 空闲时间推荐补充景点，并询问用户是否添加。
  Future<void> _promptAddRecommendations(double freeHours) async {
    final recs = _recommendToFill(freeHours);
    if (recs.isEmpty) {
      await _showRoughPlans(null);
      return;
    }
    setState(() {
      _pendingRecs = recs;
      _awaitingRecs = true;
      _messages.add(ChatMessage(
        role: 'assistant',
        content: _recommendationText(recs, freeHours),
      ));
    });
    _scrollToBottom();
  }

  String _recommendationText(List<Waypoint> recs, double freeHours) {
    final buf = StringBuffer('你有约 ${_fmtHours(freeHours)} 的空闲时间，为你推荐补充景点：\n');
    for (final w in recs) {
      buf.writeln('· ${w.city} ${w.attraction.name}（约 ${_fmtHours(w.attraction.playHours)}）');
    }
    buf.write('回复「添加」把这些景点加入行程；回复「不用了」直接生成。');
    return buf.toString();
  }

  /// 处理用户对推荐景点的回复；返回是否已处理。
  Future<bool> _handleRecsReply(String q) async {
    // 拒绝
    if (RegExp(r'不用|不要|不需要|跳过|算了|免了|不加').hasMatch(q)) {
      _pendingRecs = [];
      setState(() => _messages.add(const ChatMessage(
          role: 'assistant', content: '好的，不添加。直接给你攻略预览。')));
      _scrollToBottom();
      await _showRoughPlans(null);
      return true;
    }
    // 同意（含「添加」「加」「好」「可以」「行」「要」「生成」等）
    if (q.contains('添加') || q.contains('加') || _isGenerateCommand(q)) {
      final added = <Waypoint>[];
      setState(() {
        for (final w in _pendingRecs) {
          final dup = _selected
              .any((s) => s.attraction.name == w.attraction.name && s.city == w.city);
          if (!dup) {
            _selected.add(w);
            added.add(w);
          }
        }
        _messages.add(ChatMessage(
          role: 'assistant',
          content: added.isEmpty
              ? '这些景点已在你的行程里了，直接给你攻略预览。'
              : '已把 ${added.length} 个推荐景点加入行程 ✅。接下来给你攻略预览。',
        ));
      });
      _pendingRecs = [];
      _scrollToBottom();
      await _showRoughPlans(null);
      return true;
    }
    return false;
  }

  /// 只选了城市、没选景点时：推荐这些城市的热门景点弹窗让用户多选，选好后按所选景点生成。
  Future<void> _recommendAndPickAttractions() async {
    final repo = DataRepository.instance;
    final candidates = <Waypoint>[];
    final seen = <String>{};
    for (final c in widget.seedCities) {
      for (final a in repo.attractionsOf(c)) {
        if (seen.add(a.name)) candidates.add(Waypoint(city: c, attraction: a));
      }
    }
    candidates.sort((a, b) => b.attraction.likes.compareTo(a.attraction.likes));
    final top = candidates.take(20).toList();

    final picked = await showDialog<List<Waypoint>>(
      context: context,
      builder: (_) => _AttractionPickerDialog(cities: widget.seedCities, candidates: top),
    );

    if (picked == null || picked.isEmpty) {
      setState(() => _messages.add(const ChatMessage(
          role: 'assistant',
          content: '好的，先不选。你可以直接告诉我想去哪些景点，或回复「开始生成」让我按城市自动安排。')));
      _scrollToBottom();
      return;
    }

    setState(() => _selected = picked);
    await _showRoughPlans(null);
  }

  Future<void> _generate(_Req req) async {
    final repo = DataRepository.instance;

    // 目的地：优先用对话解析结果，其次用首页已选站点，再退化为途经地所在城市
    final cities = <String>[];
    if (req.cities.isNotEmpty) {
      cities.addAll(req.cities);
    } else {
      cities.addAll(widget.seedCities);
      if (cities.isEmpty) {
        final seen = <String>{};
        for (final w in _selected) {
          if (seen.add(w.city)) cities.add(w.city);
        }
      }
    }
    if (cities.isEmpty) return;

    final attractionsByCity = <String, List<Attraction>>{};
    final hotelsByCity = <String, List<Hotel>>{};
    final foodsByCity = <String, List<Food>>{};
    for (final c in cities) {
      attractionsByCity[c] = repo.attractionsOf(c);
      hotelsByCity[c] = repo.hotelsOf(c);
      foodsByCity[c] = repo.foodsOf(c);
    }

    // 游玩天数：优先用户说的天数（均分到各城）；未指定再按景点时长估算
    final Map<String, int> daysByCity;
    if (_days > 0) {
      daysByCity = _allocateDays(cities, _days);
    } else if (_selected.isNotEmpty) {
      final wpByCity = <String, List<Attraction>>{};
      for (final w in _selected) {
        wpByCity.putIfAbsent(w.city, () => []).add(w.attraction);
      }
      daysByCity = PlanGenerator.estimateDaysByCity(wpByCity);
    } else {
      daysByCity = PlanGenerator.estimateDaysByCity(attractionsByCity);
    }
    final days = daysByCity.values.fold<int>(0, (s, d) => s + d);

    // 同步个人信息（含景点偏好 / 旅行风格 / 各档预算）
    final address = await PrefsService.loadAddress();
    final tastes = await PrefsService.loadTastes();
    final attractionPrefs = await PrefsService.loadAttractionPref();
    final travelStyle = await PrefsService.loadTravelStyle();
    final accBudget = await PrefsService.loadAccommodationBudget();
    final transBudget = await PrefsService.loadTransportBudget();
    final totalBudget = await PrefsService.loadTotalBudget();

    final departure = req.departure.isNotEmpty
        ? req.departure
        : (repo.cityFromAddress(address) ?? '北京');

    final pref = TripPreference(
      departure: departure,
      destinations: cities,
      depDate: _today(),
      days: days,
      people: req.people == 0 ? 2 : req.people,
      ageGroup: 'friends',
      tastes: tastes.isEmpty ? const ['local'] : tastes,
      hotelLevel: 'mid',
      transportPref: 'both',
      budget: req.budget == 0 ? (totalBudget > 0 ? totalBudget : 2000) : req.budget,
      address: address,
      attractionPrefs: attractionPrefs,
      travelStyle: travelStyle,
      accommodationBudget: accBudget,
      transportBudget: transBudget,
      daysByCity: daysByCity,
    );

    final plans = PlanGenerator.generatePlans(
      cities: cities,
      attractionsByCity: attractionsByCity,
      hotelsByCity: hotelsByCity,
      foodsByCity: foodsByCity,
      days: days,
      daysByCity: daysByCity,
      waypoints: _selected,
      budgetLevel: 'mid',
      preference: pref,
      legs: _legs,
      onlyStyle: _styleId,
    );

    if (!mounted) return;
    setState(() {
      _pref = pref;
      _plans = plans;
      _messages.add(ChatMessage(
        role: 'assistant',
        content: '已生成「${cities.join('→')}」行程（共 $days 天），正在打开行程详情…',
      ));
    });
  }

  /// 解析出目的地后：记录用户说的天数，进入攻略预览 + 多方案选择。
  Future<void> _onDestination(_Req req) async {
    _pendingReq = req;
    if (req.days > 0) _days = req.days;
    _legs = []; // 新规划开始：清空旧班次
    _savedHistoryId = null;
    await _showRoughPlans(req);
  }

  /// 给出一份「大概攻略」预览 + 多个方案风格，等待用户选择。
  Future<void> _showRoughPlans(_Req? req) async {
    final cities = _effectiveCities(req);
    if (cities.isEmpty) return;
    // 天数随用户所说：用户说了用用户的天数，否则按景点时长估算并固化
    final days = _days > 0 ? _days : _estimatedDays(cities);
    _days = days;
    setState(() {
      _awaitingStyle = true;
      _messages.add(ChatMessage(
        role: 'assistant',
        content: _roughPlanText(cities, days),
      ));
    });
    _scrollToBottom();
  }

  /// 未指定天数时，按各城景点时长估算总天数。
  int _estimatedDays(List<String> cities) {
    final repo = DataRepository.instance;
    final byCity = <String, List<Attraction>>{};
    for (final c in cities) {
      if (_selected.isNotEmpty) {
        byCity[c] = [for (final w in _selected) if (w.city == c) w.attraction];
      } else {
        byCity[c] = repo.attractionsOf(c);
      }
    }
    final m = PlanGenerator.estimateDaysByCity(byCity);
    return m.values.fold<int>(0, (s, d) => s + d);
  }

  /// 「大概攻略」+ 5 个方案风格选择文案。
  String _roughPlanText(List<String> cities, int days) {
    final buf = StringBuffer('收到！${cities.join('→')} · $days 天，先给你一份大概攻略：\n');
    buf.write(_roughItinerary(cities, days));
    buf.writeln('\n我准备了 5 种方案风格，回复编号（或风格名）选择：');
    const marks = ['①', '②', '③', '④', '⑤'];
    for (var i = 0; i < PlanStyle.all.length; i++) {
      final s = PlanStyle.all[i];
      buf.writeln('${marks[i]} ${s.emoji} ${s.name}：${s.desc}');
    }
    return buf.toString();
  }

  /// 按天数均分到城市，逐天列出景点（已选景点优先，否则热门景点）。
  String _roughItinerary(List<String> cities, int days) {
    final repo = DataRepository.instance;
    final alloc = _allocateDays(cities, days);
    final buf = StringBuffer();
    var day = 1;
    for (final c in cities) {
      final cd = alloc[c] ?? 1;
      final picked = [for (final w in _selected) if (w.city == c) w.attraction];
      final pool = picked.isNotEmpty
          ? picked
          : (List.of(repo.attractionsOf(c))..sort((a, b) => b.likes.compareTo(a.likes)));
      for (var i = 0; i < cd; i++) {
        final names = pool.skip(i * 3).take(3).map((a) => a.name).join('、');
        buf.writeln('Day$day（$c）：${names.isEmpty ? '自由活动' : names}');
        day++;
      }
    }
    return buf.toString();
  }

  /// 总天数尽量均分到各城市（每城至少 1 天）。
  Map<String, int> _allocateDays(List<String> cities, int days) {
    final n = cities.length;
    if (n == 0) return {};
    final base = days ~/ n;
    final rem = days % n;
    final out = <String, int>{};
    for (var i = 0; i < n; i++) {
      out[cities[i]] = base + (i < rem ? 1 : 0);
    }
    return out;
  }

  /// 处理用户对方案风格的选择；返回是否已处理。
  Future<bool> _handleStyleReply(String q) async {
    PlanStyle? chosen;
    // 优先匹配风格名 / 风格 id（避免与「2 个人」「5 天」里的数字混淆）
    for (final s in PlanStyle.all) {
      if (q.contains(s.name) || q.contains(s.id)) {
        chosen = s;
        break;
      }
    }
    // 其次匹配纯编号：整条消息仅是一个编号（如「2」或「②」）
    if (chosen == null) {
      final m = RegExp(r'^\s*([①-⑤1-5])\s*$').firstMatch(q);
      if (m != null) {
        final raw = m.group(1)!;
        final idx = '①②③④⑤'.contains(raw) ? '①②③④⑤'.indexOf(raw) : int.parse(raw) - 1;
        chosen = PlanStyle.all[idx];
      }
    }
    if (chosen == null) return false;

    _styleId = chosen.id;
    final name = chosen.name;
    final emoji = chosen.emoji;
    setState(() => _messages.add(ChatMessage(
        role: 'assistant',
        content: '好的，采用「$name」风格 $emoji。接下来确认跨城交通班次。')));
    _scrollToBottom();
    await _afterStyleChosen();
    return true;
  }

  /// 选定风格后：进入跨城班次选择。
  Future<void> _afterStyleChosen() async {
    final req = _pendingReq;
    final cities = _effectiveCities(req);
    if (cities.isNotEmpty && _legs.isEmpty) {
      await _promptLegs(req, cities);
    }
  }

  /// 确定本次规划涉及的目的地城市（优先级：对话解析 > 首页站点 > 途经地城市）。
  List<String> _effectiveCities(_Req? req) {
    if (req != null && req.cities.isNotEmpty) return req.cities;
    if (widget.seedCities.isNotEmpty) return widget.seedCities;
    final s = <String>{};
    for (final w in _selected) {
      s.add(w.city);
    }
    return s.toList();
  }

  /// 提示用户生成行程方案（信息与班次已确认）。
  void _promptGenerate() {
    setState(() {
      _awaitingConfirm = true;
      _messages.add(const ChatMessage(
        role: 'assistant',
        content: '行程信息与班次已确认 ✅。是否现在生成行程方案？回复「生成」即可。',
      ));
    });
    _scrollToBottom();
  }

  /// 构建默认班次（出发地 → 各城市 → 返回出发地，默认推荐高铁），
  /// 并提示用户点击卡片为每段挑选高铁/飞机多个班次，或回复「确认」用推荐。
  Future<void> _promptLegs(_Req? req, List<String> cities) async {
    final address = await PrefsService.loadAddress();
    final departure = (req?.departure.isNotEmpty == true)
        ? req!.departure
        : (DataRepository.instance.cityFromAddress(address) ?? '北京');
    _legs = _buildDefaultLegs(departure, cities);
    if (_legs.isEmpty) {
      _promptGenerate();
      return;
    }

    final buf = StringBuffer('接下来确认跨城交通班次 🚄✈️（默认已选推荐高铁）：\n');
    for (final l in _legs) {
      buf.writeln('${l.from} → ${l.to}：${l.label}（¥${l.price}）');
    }
    buf.write('点击下方「选择班次」卡片，可为每一段挑选高铁/飞机多个班次；'
        '或直接回复「确认」使用推荐班次。');
    setState(() {
      _awaitingLegs = true;
      _messages.add(ChatMessage(role: 'assistant', content: buf.toString()));
    });
    _scrollToBottom();
  }

  /// 处理用户对班次确认的回复；返回是否已处理。
  Future<bool> _handleLegsReply(String q) async {
    if (q.contains('飞机') || q.contains('航班')) {
      _legs = [for (final l in _legs) _toFlightLeg(l)];
      await _showLegsAfterChange('已全部改为航班 ✈️：');
      return true;
    }
    if (q.contains('高铁') || q.contains('火车')) {
      await _showLegsAfterChange('已保持高铁 🚄：');
      return true;
    }
    if (_isGenerateCommand(q)) {
      setState(() => _messages.add(const ChatMessage(role: 'assistant', content: '好的，班次已确认。')));
      _scrollToBottom();
      _promptGenerate();
      return true;
    }
    return false;
  }

  /// 调整班次后重新展示，并再次询问确认。
  Future<void> _showLegsAfterChange(String prefix) async {
    final buf = StringBuffer('$prefix\n');
    for (final l in _legs) {
      buf.writeln('${l.from} → ${l.to}：${l.label}（¥${l.price}）');
    }
    buf.write('回复「确认」继续；或再回复「坐飞机」/「高铁」调整。');
    setState(() {
      _awaitingLegs = true;
      _messages.add(ChatMessage(role: 'assistant', content: buf.toString()));
    });
    _scrollToBottom();
  }

  /// 构建「出发地 → 城市… → 出发地」的默认高铁班次列表。
  List<TransitLeg> _buildDefaultLegs(String departure, List<String> cities) {
    final route = [departure, ...cities, departure];
    final legs = <TransitLeg>[];
    for (var i = 0; i < route.length - 1; i++) {
      if (route[i] != route[i + 1]) {
        legs.add(_defaultLeg(route[i], route[i + 1]));
      }
    }
    return legs;
  }

  TransitLeg _defaultLeg(String from, String to) {
    final t = TransitService.trainRoutes(from, to).first;
    return TransitLeg(
      from: from,
      to: to,
      mode: 'train',
      label: '${t.trainNo} ${t.depTime}-${t.arrTime}',
      price: t.secondSeat,
    );
  }

  TransitLeg _toFlightLeg(TransitLeg leg) {
    final f = TransitService.flightOptions(leg.from, leg.to).first;
    return TransitLeg(
      from: leg.from,
      to: leg.to,
      mode: 'flight',
      label: '${f.flightNo} ${f.depTime}-${f.arrTime}',
      price: f.economyPrice,
    );
  }

  /// 用户确认后：生成单一行程、自动保存到「我的行程」并直接进入详情页。
  Future<void> _generateConfirmed() async {
    setState(() => _loading = true);
    await _generate(
        _pendingReq ?? (departure: '', cities: const [], days: 0, people: 0, budget: 0));
    if (!mounted) return;
    setState(() => _loading = false);
    _scrollToBottom();
    await _saveAndOpenPlan();
  }

  /// 生成后自动保存到「我的行程」，再打开详情页。
  Future<void> _saveAndOpenPlan() async {
    if (_pref == null || _plans.isEmpty) return;
    final plan = _plans.first;
    try {
      _savedHistoryId = await DatabaseService.addHistory(
        city: _pref!.destinationLabel,
        days: plan.totalDays,
        styleName: plan.style.name,
        recommendation: plan.recommendation,
        planJson: jsonEncode(plan.toJson()),
      );
    } catch (_) {
      // 保存失败不阻塞跳转详情
    }
    if (!mounted) return;
    _openPlanDetail();
  }

  /// 直接进入单一行程详情页（不再展示多风格方案列表）。
  void _openPlanDetail() {
    if (_pref == null || _plans.isEmpty) return;
    Navigator.of(context).pushNamed(
      Routes.planDetail,
      arguments: (
        plan: _plans.first,
        city: _pref!.destinationLabel,
        budget: _pref!.budget,
        historyId: _savedHistoryId,
      ),
    );
  }

  /// 逐段弹出班次选择（高铁/飞机 → 具体班次），全部确认后提示生成。
  Future<void> _showLegPicker() async {
    for (var i = 0; i < _legs.length; i++) {
      final leg = _legs[i];
      final mode = await showModalBottomSheet<String>(
        context: context,
        builder: (ctx) => SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                title: Text('${leg.from} → ${leg.to}',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: const Text('选择出行方式'),
              ),
              ListTile(
                leading: const Icon(Icons.train, color: Colors.teal),
                title: const Text('高铁'),
                onTap: () => Navigator.pop(ctx, 'train'),
              ),
              ListTile(
                leading: const Icon(Icons.flight, color: Colors.blue),
                title: const Text('飞机'),
                onTap: () => Navigator.pop(ctx, 'flight'),
              ),
            ],
          ),
        ),
      );
      if (!mounted) return;
      if (mode == null) return; // 取消：保持推荐班次并结束
      final picked = await _pickScheduleSheet(leg.from, leg.to, mode);
      if (!mounted) return;
      if (picked != null) {
        setState(() => _legs[i] = picked);
      }
    }
    if (!mounted) return;
    setState(() => _awaitingLegs = false);
    _promptGenerate();
  }

  /// 某一段的班次列表（多个高铁/航班供选择）。
  Future<TransitLeg?> _pickScheduleSheet(String from, String to, String mode) {
    final isTrain = mode == 'train';
    return showModalBottomSheet<TransitLeg>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(children: [
                Icon(isTrain ? Icons.train : Icons.flight, color: Colors.teal),
                const SizedBox(width: 8),
                Text('$from → $to · ${isTrain ? '高铁' : '航班'}班次',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ]),
            ),
            const Divider(height: 1),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 420),
              child: ListView(
                shrinkWrap: true,
                children: [
                  if (isTrain)
                    for (final t in TransitService.trainRoutes(from, to))
                      _scheduleTile(ctx, Icons.train, Colors.teal,
                          '${t.trainNo}  ${t.depTime} → ${t.arrTime}',
                          '${t.depStation} - ${t.arrStation} · ${t.duration}',
                          '¥${t.secondSeat}',
                          TransitLeg(from: from, to: to, mode: 'train',
                              label: '${t.trainNo} ${t.depTime}-${t.arrTime}', price: t.secondSeat))
                  else
                    for (final f in TransitService.flightOptions(from, to))
                      _scheduleTile(ctx, Icons.flight, Colors.blue,
                          '${f.flightNo}  ${f.depTime} → ${f.arrTime}',
                          '${f.airline} · ${f.duration}',
                          '¥${f.economyPrice}',
                          TransitLeg(from: from, to: to, mode: 'flight',
                              label: '${f.flightNo} ${f.depTime}-${f.arrTime}', price: f.economyPrice)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _scheduleTile(BuildContext ctx, IconData icon, Color color, String title,
      String subtitle, String price, TransitLeg leg) {
    return ListTile(
      leading: Icon(icon, color: color),
      title: Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 12)),
      trailing: Text(price,
          style: TextStyle(fontSize: 14, color: Colors.orange.shade800, fontWeight: FontWeight.w700)),
      onTap: () => Navigator.pop(ctx, leg),
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 行程定制'),
        actions: [
          TextButton.icon(
            onPressed: () {
              Navigator.of(context).pushNamed(Routes.input);
            },
            icon: const Icon(Icons.edit_note, size: 18),
            label: const Text('手动填写'),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length +
                  (_loading ? 1 : 0) +
                  (_awaitingLegs ? 1 : 0) +
                  (_plans.isEmpty ? 0 : 1),
              itemBuilder: (_, i) {
                if (i < _messages.length) return _bubble(_messages[i]);
                var offset = _messages.length;
                if (_loading) {
                  if (i == offset) return const _TypingBubble();
                  offset += 1;
                }
                if (_awaitingLegs) {
                  if (i == offset) return _legCard();
                  offset += 1;
                }
                return _planCard();
              },
            ),
          ),
          _quickBar(),
          _inputBar(),
        ],
      ),
    );
  }

  Widget _legCard() {
    return Card(
      margin: const EdgeInsets.only(top: 4, bottom: 10),
      color: Colors.blue.shade50,
      child: ListTile(
        leading: const Icon(Icons.directions_transit, color: Colors.blue),
        title: const Text('选择跨城班次', style: TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('共 ${_legs.length} 段 · 点击为每段挑选高铁/飞机班次'),
        trailing: const Icon(Icons.chevron_right, color: Colors.blue),
        onTap: _showLegPicker,
      ),
    );
  }

  Widget _planCard() {
    return Card(
      margin: const EdgeInsets.only(top: 4, bottom: 10),
      color: Colors.teal.shade50,
      child: ListTile(
        leading: const Icon(Icons.map, color: Colors.teal),
        title: const Text('查看行程', style: TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('${_pref?.destinationDaysLabel ?? ''} · 共 ${_pref?.days ?? 0} 天'),
        trailing: const Icon(Icons.chevron_right, color: Colors.teal),
        onTap: _openPlanDetail,
      ),
    );
  }

  Widget _bubble(ChatMessage m) {
    final isUser = m.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        decoration: BoxDecoration(
          color: isUser ? Theme.of(context).colorScheme.primary : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 16),
          ),
        ),
        child: Text(
          m.content,
          style: TextStyle(color: isUser ? Colors.white : Colors.black87, height: 1.5),
        ),
      ),
    );
  }

  /// 快捷示例
  Widget _quickBar() {
    final prompts = <String>[
      if (widget.seedCities.isNotEmpty || _selected.isNotEmpty) '开始生成',
      ..._quickPrompts,
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      child: Wrap(
        spacing: 8,
        runSpacing: 6,
        children: [
          for (final p in prompts)
            ActionChip(
              label: Text(p, style: const TextStyle(fontSize: 12)),
              onPressed: _loading ? null : () => _send(p),
            ),
        ],
      ),
    );
  }

  Widget _inputBar() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: BoxDecoration(color: Colors.white, boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 6),
        ]),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _input,
                textInputAction: TextInputAction.send,
                onSubmitted: _send,
                decoration: InputDecoration(
                  hintText: '描述你的行程，如「从北京去上海玩3天」…',
                  filled: true,
                  fillColor: const Color(0xFFF2F4F7),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: _loading ? null : () => _send(_input.text),
              icon: const Icon(Icons.send_rounded),
              tooltip: '发送',
            ),
          ],
        ),
      ),
    );
  }
}

/// AI 正在输入的气泡
class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    return const Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: EdgeInsets.only(bottom: 10),
        child: SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
    );
  }
}

/// 把游玩时长格式化为「X 小时」（整数不带小数）。
String _fmtHours(double h) =>
    h == h.roundToDouble() ? '${h.toInt()} 小时' : '${h.toStringAsFixed(1)} 小时';

/// 景点多选弹窗：展示 AI 推荐的热门景点，用户勾选后返回所选 [Waypoint] 列表。
class _AttractionPickerDialog extends StatefulWidget {
  final List<String> cities;
  final List<Waypoint> candidates;
  const _AttractionPickerDialog({required this.cities, required this.candidates});

  @override
  State<_AttractionPickerDialog> createState() => _AttractionPickerDialogState();
}

class _AttractionPickerDialogState extends State<_AttractionPickerDialog> {
  final Set<int> _picked = {};

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('AI 推荐景点（${widget.cities.join('、')}）'),
      content: SizedBox(
        width: 380,
        height: 440,
        child: widget.candidates.isEmpty
            ? const Center(child: Text('该城市暂无景点数据'))
            : ListView(
                children: [
                  for (var i = 0; i < widget.candidates.length; i++)
                    CheckboxListTile(
                      value: _picked.contains(i),
                      onChanged: (v) => setState(() {
                        if (v == true) {
                          _picked.add(i);
                        } else {
                          _picked.remove(i);
                        }
                      }),
                      title: Text(widget.candidates[i].attraction.name,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text(
                          '${widget.candidates[i].city} · ${_fmtHours(widget.candidates[i].attraction.playHours)}'),
                      controlAffinity: ListTileControlAffinity.leading,
                      dense: true,
                    ),
                ],
              ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
        FilledButton(
          onPressed: () {
            final out = <Waypoint>[for (final i in _picked) widget.candidates[i]];
            Navigator.pop(context, out);
          },
          child: Text('确定（${_picked.length}）'),
        ),
      ],
    );
  }
}
