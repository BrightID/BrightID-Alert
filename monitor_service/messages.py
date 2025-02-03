ISSUE_MESSAGES = {
    # Node issues
    "node_state_down": "⚠️ BrightID node is not reporting its state.\nNode: {}",
    "node_state_resolved": "✅ BrightID node state issue resolved.\nNode: {}",
    "node_balance_low": "⚠️ BrightID node has low Eidi balance.\nNode: {}\nBalance: {:.2f} Eidi\nThreshold: {} Eidi",
    "node_balance_resolved": "✅ BrightID node Eidi balance issue resolved.\nNode: {}",
    "receiver_service_down": "⚠️ BrightID node consensus receiver service is offline.\nNode: {}",
    "receiver_service_resolved": "✅ BrightID node consensus receiver service issue resolved.\nNode: {}",
    "scorer_service_down": "⚠️ BrightID node scorer service is offline.\nNode: {}",
    "scorer_service_resolved": "✅ BrightID node scorer service issue resolved.\nNode: {}",
    "sender_service_down": "⚠️ BrightID node consensus sender service is offline.\nNode: {}",
    "sender_service_resolved": "✅ BrightID node consensus sender service issue resolved.\nNode: {}",
    "profile_service_down": "⚠️ BrightID node profile service is unavailable.\nProfile Service: {}",
    "profile_service_resolved": "✅ BrightID node profile service issue resolved.\nProfile Service: {}",
    "node_version_outdated": "⚠️ BrightID node is outdated.\nNode: {}\nVersion: v{}\nLast Version: v{}",
    "node_version_resolved": "✅ BrightID node updated to latest version.\nNode: {}",
    # Updater service issues
    "apps_updater_down": "⚠️ BrightID node apps updater service is offline.\nNode: {}",
    "apps_updater_resolved": "✅ BrightID node apps updater service issue resolved.\nNode: {}",
    "sp_updater_down": "⚠️ BrightID node sponsorship updater service is offline.\nNode: {}",
    "sp_updater_resolved": "✅ BrightID node sponsorship updater service issue resolved.\nNode: {}",
    "seed_groups_updater_down": "⚠️ BrightID node seed group updater service is offline.\nNode: {}",
    "seed_groups_updater_resolved": "✅ BrightID node seed group updater service issue resolved.\nNode: {}",
    # System services issues
    "recovery_service_down": "⚠️ BrightID recovery service is unavailable.",
    "recovery_service_resolved": "✅ BrightID recovery service issue resolved.",
    "backup_service_down": "⚠️ BrightID node backup service is offline.",
    "backup_service_resolved": "✅ BrightID node backup service issue resolved.",
    # Application issues
    "app_sp_balance_low": "⚠️ App has low unused Sponsorships.\nApp: {}\nBalance: {}",
    "app_sp_balance_resolved": "✅ App Sponsorships balance issue resolved.\nApp: {}",
}
