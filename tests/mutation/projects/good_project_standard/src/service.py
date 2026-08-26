"""Service layer — business logic orchestration."""


class Service:
    """Business service depending on repository via constructor injection."""

    def __init__(self, repository):
        self.repository = repository

    def get_user(self, user_id):
        return self.repository.find(user_id)

    def create_user(self, name):
        return self.repository.save(name)


class UserRepository:
    """Concrete repository implementation."""

    def find(self, user_id):
        return {"id": user_id, "name": "user"}

    def save(self, name):
        return {"id": 1, "name": name}