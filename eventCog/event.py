from threading import Timer


class Event:
    def __init__(self, id, title, description, date, notifyBefore):
        self.id = id
        self.title = title
        self.description = description
        self.date = date
        self.members = []
        self.notifyTimer = Timer(date - notifyBefore, self.sendMessage)
        self.notifyTimer.start()

    def sendMessage(self):
        for member, notify in self.members:
            if notify:
                # send private message notifying
                print 'test'
        # run function in eventscog to remove this specific event from object. (static)

    def addMember(self, member, notify):
        self.members.append((member, notify))
