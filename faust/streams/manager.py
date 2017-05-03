import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Set, Sequence, MutableMapping, Tuple, cast
from ..types import Message, TopicPartition
from ..types.app import AppT
from ..types.streams import StreamT, StreamManagerT
from ..types.transports import ConsumerCallback, ConsumerT
from ..utils.services import Service
from .stream import Stream

__flake8_Dict_is_used: Dict    # XXX flake8 bug
__flake8_Tuple_is_used: Tuple  # XXX flake8 bug


class StreamManager(StreamManagerT, Service):
    """Manages the Streams that make up an app.

    - Consumes messages from topic using a single consumer.
    - Forwards messages to all streams subscribing to a topic.
    """

    #: Fast index to see if stream is registered.
    _streams: Set[StreamT]

    #: Map str topic to set of streams that should get a copy
    #: of each message sent to that topic.
    _topicmap: MutableMapping[str, Set[StreamT]]

    def __init__(self, app: AppT, **kwargs: Any) -> None:
        self.app = app
        self.consumer = None
        self._streams = set()
        self._topicmap = defaultdict(set)
        super().__init__(**kwargs)

    def ack_message(self, message: Message) -> None:
        if not message.acked:
            return self.ack_offset(
                TopicPartition(message.topic, message.partition),
                message.offset,
            )
        message.acked = True

    def ack_offset(self, tp: TopicPartition, offset: int) -> None:
        return self.consumer.ack(tp, offset)

    def add_stream(self, stream: StreamT) -> None:
        if stream in self._streams:
            raise ValueError('Stream already registered with app')
        self._streams.add(stream)
        self.beacon.add(stream)  # connect to beacon

    async def update(self) -> None:
        self._compile_pattern()
        await self.consumer.subscribe(self._pattern)

    def _compile_message_handler(self) -> ConsumerCallback:
        # topic str -> list of Stream
        get_streams_for_topic = self._topicmap.__getitem__

        async def on_message(message: Message) -> None:
            # when a message is received we find all streams
            # that subscribe to this message
            streams = list(get_streams_for_topic(message.topic))

            # we increment the reference count for this message in bulk
            # immediately, so that nothing will get a chance to decref to
            # zero before we've had the chance to pass it to all streams.
            message.incref_bulk(streams)

            # Then send it to each streams inbox,
            # for Stream.__anext__ to pick up.
            for stream in streams:
                await stream.inbox.put(message)
        return on_message

    async def on_start(self) -> None:
        self.add_future(self._delayed_start())

    async def _delayed_start(self) -> None:
        # wait for tasks to start streams
        await asyncio.sleep(2.0, loop=self.loop)

        # then register topics etc.
        self._compile_pattern()
        self._on_message = self._compile_message_handler()
        self.consumer = self._create_consumer()
        await self.consumer.subscribe(self._pattern)
        await self.consumer.start()

    async def on_stop(self) -> None:
        if self.consumer:
            await self.consumer.stop()

    def _create_consumer(self) -> ConsumerT:
        return self.app.transport.create_consumer(
            callback=self._on_message,
            on_partitions_revoked=self._on_partitions_revoked,
            on_partitions_assigned=self._on_partitions_assigned,
            beacon=self.beacon,
        )

    def _compile_pattern(self) -> None:
        self._topicmap.clear()

        consolidated_streams: List[Stream] = []
        ungrouped_streams: List[Stream] = []

        # Group streams by task group+index.
        streams: Dict[Tuple[int, int], List[Stream]] = defaultdict(list)
        for stream in cast(List[Stream], self._streams):
            if stream.task_group is not None:
                streams[(stream.task_group, stream.task_index)].append(stream)
            else:
                # move streams from unknown task groups into separate list.
                ungrouped_streams.append(stream)

        # Streams with the same group index should share the same inbox
        for _, group_streams in streams.items():
            consolidated_streams.append(group_streams[0])
            # group_streams[0].inbox is shared with all streams
            for s in group_streams[1:]:
                s.inbox = group_streams[0].inbox

        # add back all streams with task_group=None
        consolidated_streams.extend(ungrouped_streams or [])

        for stream in consolidated_streams:
            if stream.active:
                for topic in stream._topicmap:
                    self._topicmap[topic].add(stream)
        self._pattern = '|'.join(self._topicmap)

    def _on_partitions_assigned(self,
                                assigned: Sequence[TopicPartition]) -> None:
        ...

    def _on_partitions_revoked(self,
                               revoked: Sequence[TopicPartition]) -> None:
        ...

    @property
    def label(self) -> str:
        return '{}({})'.format(
            type(self).__name__, len(self._streams))
