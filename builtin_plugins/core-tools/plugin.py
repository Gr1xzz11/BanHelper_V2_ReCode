class Plugin:
    def activate(self, context):
        self.context = context
        context.log("INFO", "Core Tools запущен")
        context.register_action(
            "check",
            lambda payload: context.show_status("Plugin API работает", 3000),
            "Проверить Plugin API",
        )
        context.register_action(
            "mode_ft",
            lambda payload: self._set_mode("FT"),
            "Переключить режим на FT",
        )
        context.register_action(
            "mode_rw",
            lambda payload: self._set_mode("RW"),
            "Переключить режим на RW",
        )

    def _set_mode(self, mode):
        self.context.command("save_settings", {"manual_mode": mode})
        self.context.show_status(f"Режим переключён на {mode}", 3000)
        return {"mode": mode}

    def deactivate(self):
        self.context.log("INFO", "Core Tools остановлен")
