from __future__ import annotations

from typing import Any

from .contracts import (
    ProviderCapability,
    ProviderCapabilityMismatchError,
    ProviderDescriptor,
    ProviderRegistrationError,
    ProviderUnavailableError,
    UnknownProviderError,
)


class ProviderRegistry:
    """Discoverable, capability-safe catalog of raw provider implementations."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ProviderDescriptor] = {}
        self._providers: dict[str, object | None] = {}

    def register(self, descriptor: ProviderDescriptor, provider: object | None) -> None:
        if not isinstance(descriptor, ProviderDescriptor):
            raise TypeError("descriptor must be a ProviderDescriptor")
        if descriptor.provider_id in self._descriptors:
            raise ProviderRegistrationError(f"duplicate provider id: {descriptor.provider_id}")
        if descriptor.status == "unavailable":
            if provider is not None:
                raise ProviderRegistrationError("unavailable providers must not register an implementation")
        elif provider is None:
            raise ProviderRegistrationError("available or experimental providers require an implementation")
        self._descriptors[descriptor.provider_id] = descriptor
        self._providers[descriptor.provider_id] = provider

    def descriptor(self, provider_id: str) -> ProviderDescriptor:
        key = str(provider_id).strip()
        try:
            return self._descriptors[key]
        except KeyError as exc:
            raise UnknownProviderError(f"unknown provider id: {provider_id}") from exc

    def descriptors(self, capability: ProviderCapability | None = None) -> list[ProviderDescriptor]:
        if capability is None:
            return list(self._descriptors.values())
        expected = _coerce_capability(capability)
        return [descriptor for descriptor in self._descriptors.values() if descriptor.capability == expected]

    def resolve(self, provider_id: str, capability: ProviderCapability | None = None) -> Any:
        descriptor = self.descriptor(provider_id)
        if capability is not None:
            expected = _coerce_capability(capability)
            if descriptor.capability != expected:
                raise ProviderCapabilityMismatchError(
                    f"provider {descriptor.provider_id} has capability {descriptor.capability.value}, "
                    f"not {expected.value}"
                )
        provider = self._providers[descriptor.provider_id]
        if descriptor.status == "unavailable" or provider is None:
            raise ProviderUnavailableError(f"provider is unavailable: {descriptor.provider_id}")
        return provider


def _coerce_capability(capability: ProviderCapability) -> ProviderCapability:
    try:
        return ProviderCapability(capability)
    except ValueError as exc:
        raise ValueError(f"unsupported provider capability: {capability}") from exc
