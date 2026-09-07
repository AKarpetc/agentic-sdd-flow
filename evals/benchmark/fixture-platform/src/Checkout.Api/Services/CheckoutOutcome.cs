using Platform.Contracts;

namespace Checkout.Api.Services;

/// <summary>Either the completed checkout or the reason it stopped.</summary>
internal sealed record CheckoutOutcome(CheckoutResult? Result, CheckoutFailure? Failure);
