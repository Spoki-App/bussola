import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from rtool.config import RepoConfig
from rtool.git import BlobReader, BlobRef
from rtool.globs import matches_any
from rtool.units.extractors.base import Extractor
from rtool.units.extractors.fallback import binary_unit, file_unit, submodule_unit
from rtool.units.model import Unit
from rtool.units.registry import EXTRACTORS_BY_SUFFIX, extractor_for

BINARY_SNIFF_BYTES = 8000
FALLBACK_EXTRACTOR = "file"
FALLBACK_VERSION = 1


@dataclass(frozen=True)
class CacheKey:
    object_id: str
    extractor: str
    version: int


class UnitCache(Protocol):
    def get(self, key: CacheKey) -> list[Unit] | None: ...

    def put(self, key: CacheKey, units: list[Unit]) -> None: ...


class InMemoryUnitCache:
    def __init__(self) -> None:
        self._entries: dict[CacheKey, list[Unit]] = {}

    def get(self, key: CacheKey) -> list[Unit] | None:
        return self._entries.get(key)

    def put(self, key: CacheKey, units: list[Unit]) -> None:
        self._entries[key] = units


class FileUnitExtractor:
    def __init__(self, config: RepoConfig, cache: UnitCache | None = None) -> None:
        self.config = config
        self._cache: UnitCache = cache if cache is not None else InMemoryUnitCache()

    def signature(self) -> str:
        extractors = sorted((suffix, extractor.name, extractor.version) for suffix, extractor in EXTRACTORS_BY_SUFFIX.items())
        rules = [FALLBACK_EXTRACTOR, FALLBACK_VERSION, extractors, self.config.file_level]
        return hashlib.sha256(json.dumps(rules).encode()).hexdigest()

    def units_for(self, blob: BlobRef, reader: BlobReader) -> list[Unit]:
        if blob.is_submodule:
            return [submodule_unit(blob.object_id)]
        extractor = None if matches_any(blob.path, self.config.file_level) else extractor_for(blob.path)
        key = CacheKey(blob.object_id, *(_identity(extractor)))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        units = _extract(extractor, blob.object_id, reader.read(blob.object_id))
        self._cache.put(key, units)
        return units


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:BINARY_SNIFF_BYTES]


def _identity(extractor: Extractor | None) -> tuple[str, int]:
    return (extractor.name, extractor.version) if extractor else (FALLBACK_EXTRACTOR, FALLBACK_VERSION)


def _extract(extractor: Extractor | None, object_id: str, data: bytes) -> list[Unit]:
    if is_binary(data):
        return [binary_unit(object_id)]
    if extractor is None:
        return [file_unit(data)]
    units = extractor.extract(data)
    return [file_unit(data)] if units is None else units
