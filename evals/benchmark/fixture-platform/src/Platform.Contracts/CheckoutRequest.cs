namespace Platform.Contracts;

/// <summary>A basket presented to the checkout gateway; <paramref name="RequestId"/> identifies one attempt.</summary>
public sealed record CheckoutRequest(long CustomerId, string RequestId, IReadOnlyList<CheckoutLine> Lines);
