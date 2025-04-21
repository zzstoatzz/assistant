from atproto import Client, client_utils, models

from app.settings import settings

bluesky_client: Client | None = None


def init_bluesky_client():
    global bluesky_client
    if bluesky_client is None:
        client = Client()
        client.login(settings.atproto.handle, settings.atproto.password)
        bluesky_client = client.with_bsky_chat_proxy()
    return bluesky_client


def send_dm_via_atproto(message: str, link: str | None = None) -> None:
    """Send a direct message to the configured recipient via atproto/Bluesky. Not yet implemented."""
    client = init_bluesky_client()
    dm = client.chat.bsky.convo
    convo = dm.get_convo_for_members(
        models.ChatBskyConvoGetConvoForMembers.Params(members=[settings.atproto.recipient_did]),
    ).convo
    if link:
        text_builder = client_utils.TextBuilder().text(message).link('View', link)
        data = models.ChatBskyConvoSendMessage.Data(
            convo_id=convo.id,
            message=models.ChatBskyConvoDefs.MessageInput(
                text=text_builder.build_text(),
                facets=text_builder.build_facets(),
            ),
        )
    else:
        data = models.ChatBskyConvoSendMessage.Data(
            convo_id=convo.id,
            message=models.ChatBskyConvoDefs.MessageInput(
                text=message,
            ),
        )

    dm.send_message(data)
