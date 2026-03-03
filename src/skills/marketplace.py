"""
Маркетплейс навыков Argos (в разработке)
"""
class SkillMarketplace:
    def __init__(self, core):
        self.core = core
        self.skills = []

    def list_skills(self):
        # TODO: получить список доступных навыков из GitHub/локально
        return self.skills

    def install_skill(self, name):
        # TODO: установка навыка по имени
        return f"Навык {name} установлен (заглушка)"

    def remove_skill(self, name):
        # TODO: удаление навыка
        return f"Навык {name} удалён (заглушка)"
