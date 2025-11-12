import uuid
from typing import Iterable, List
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec

class Codec(PayloadCodec):

    min_bytes = 1000000  # 1MB default

    def __init__(self, min_bytes: int, path: str, ):
        self.min_bytes = min_bytes
        self.path = path

    async def encode(self, payloads: Iterable[Payload]) -> List[Payload]:
        out: List[Payload] = []
        for p in payloads:
            if p.ByteSize() > self.min_bytes:
                encoded = await self.encode_payload(p)
                out.append(encoded)
            else:
                new_payload = Payload()
                new_payload.CopyFrom(p)
                out.append(new_payload)

        return out

    async def decode(self, payloads: Iterable[Payload]) -> List[Payload]:
        out: List[Payload] = []
        for p in payloads:
            if p.metadata.get("temporal.io/oversize-payload-codec", b"").decode() != "v1":
                new_payload = Payload()
                new_payload.CopyFrom(p)
                out.append(new_payload)
                continue
            file_key = p.data.decode("utf-8")
            with open(f"{self.path}{file_key}.txt", "rb") as file:
                content = file.read()
                payload = Payload.FromString(content)
                out.append(payload)
        return out

    async def encode_payload(self, payload: Payload) -> Payload:
        file_key = str(uuid.uuid4())
        with open(f"{self.path}{file_key}.txt", "wb") as new_file:
            new_file.write(payload.SerializeToString())
        out = Payload(
            metadata={
                "encoding": b"binary/oversize-payload-codec",
                "temporal.io/oversize-payload-codec": b"v1",
            },
            data=file_key.encode("utf-8"),
        )
        return out