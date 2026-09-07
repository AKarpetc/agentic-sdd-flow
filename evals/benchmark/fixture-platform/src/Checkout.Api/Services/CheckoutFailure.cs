namespace Checkout.Api.Services;

/// <summary>Why a checkout could not complete, in the shape the endpoint answers with.</summary>
internal sealed record CheckoutFailure(int StatusCode, string Title, string Detail);
