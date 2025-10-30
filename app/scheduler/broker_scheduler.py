

async def updateBrokerToken():
    try:
        await user = UserModel.get(id)

        if not user:
            logging.info('user not found in db')

        broker = UpstoxSdk()

        broker    

