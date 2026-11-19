import 'package:flutter/material.dart';

import 'models/models.dart';
import 'pages/attraction_detail_page.dart';
import 'pages/chat_page.dart';
import 'pages/city_detail_page.dart';
import 'pages/edit_page.dart';
import 'pages/home_shell.dart';
import 'pages/input_page.dart';
import 'pages/plan_chat_page.dart';
import 'pages/plan_detail_page.dart';
import 'pages/plan_list_page.dart';
import 'pages/settings_page.dart';
import 'pages/transit_page.dart';
import 'services/waypoints.dart';

/// 命名路由常量与集中式路由表（onGenerateRoute）。
///
/// 页面间跳转统一通过 [Navigator.pushNamed] + [Routes.xxx] 完成，
/// 复杂对象（Plan / Attraction / TripPreference 等）经 arguments 以 record 传递，
/// 集中管理便于维护与扩展。
class Routes {
  Routes._();

  static const String home = '/home';
  static const String chat = '/chat';
  static const String settings = '/settings';
  static const String transit = '/transit';
  static const String planChat = '/plan-chat';
  static const String cityDetail = '/city-detail';
  static const String attractionDetail = '/attraction-detail';
  static const String planList = '/plan-list';
  static const String planDetail = '/plan-detail';
  static const String edit = '/edit';
  static const String input = '/input';

  /// 集中式路由表：根据 [settings.name] 构建目标页面。
  static Route<dynamic> onGenerateRoute(RouteSettings routeSettings) {
    final args = routeSettings.arguments;
    Widget page;
    switch (routeSettings.name) {
      case home:
        page = const HomeShell();
        break;
      case chat:
        page = ChatPage(about: args as Attraction?);
        break;
      case settings:
        page = const SettingsPage();
        break;
      case transit:
        page = const TransitPage();
        break;
      case planChat:
        final a = args as ({List<String> cities, List<Waypoint> waypoints});
        page = PlanChatPage(seedCities: a.cities, seedWaypoints: a.waypoints);
        break;
      case cityDetail:
        page = CityDetailPage(city: args as City);
        break;
      case attractionDetail:
        final a = args as ({String city, Attraction attraction});
        page = AttractionDetailPage(city: a.city, attraction: a.attraction);
        break;
      case planList:
        final a = args as ({TripPreference pref, List<Plan> plans, String? aiText});
        page = PlanListPage(pref: a.pref, plans: a.plans, aiText: a.aiText);
        break;
      case planDetail:
        final a = args as ({Plan plan, String city, int budget, int? historyId});
        page = PlanDetailPage(plan: a.plan, city: a.city, budget: a.budget, historyId: a.historyId);
        break;
      case edit:
        final a = args as ({Plan plan, String city, int? historyId});
        page = EditPage(plan: a.plan, city: a.city, historyId: a.historyId);
        break;
      case input:
        page = const InputPage();
        break;
      default:
        page = const Scaffold(body: Center(child: Text('未知路由')));
    }
    return MaterialPageRoute(builder: (_) => page, settings: routeSettings);
  }
}
