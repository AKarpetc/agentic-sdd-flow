using Platform.Contracts;

namespace Checkout.Api.Clients;

/// <summary>What inventory answered to a reservation: the hold it granted, or the status it refused with.</summary>
internal sealed record ReservationAttempt(ReservationResult? Reservation, int StatusCode);
