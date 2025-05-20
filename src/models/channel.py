# SegmentChatClient/src/models/channel.py
class Channel:
    def __init__(self, id: str, name: str, owner_id: str):
        self.id = id
        self.name = name
        self.owner_id = owner_id
    
    def __str__(self):
        return f"Channel(id={self.id}, name={self.name})"

    def __repr__(self):
        return self.__str__()