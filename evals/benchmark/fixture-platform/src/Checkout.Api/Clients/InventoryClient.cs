using System.Net.Http.Json;
using Platform.Contracts;

namespace Checkout.Api.Clients;

/// <summary>Talks to inventory over HTTP; the base address comes from Services:Inventory:BaseUrl.</summary>
internal sealed class InventoryClient : IInventoryClient
{
    private readonly HttpClient _http;

    public InventoryClient(HttpClient http)
    {
        _http = http;
    }

    public async Task<ReservationAttempt> ReserveAsync(string sku, int quantity, CancellationToken cancellationToken)
    {
        using var response = await _http.PostAsJsonAsync("/api/reservations", new ReservationRequest(sku, quantity), cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return new ReservationAttempt(null, (int)response.StatusCode);
        }

        var reservation = await response.Content.ReadFromJsonAsync<ReservationResult>(cancellationToken);
        return new ReservationAttempt(reservation, (int)response.StatusCode);
    }

    public async Task ReleaseAsync(string reservationId, CancellationToken cancellationToken)
    {
        using var response = await _http.DeleteAsync($"/api/reservations/{reservationId}", cancellationToken);
        response.EnsureSuccessStatusCode();
    }
}
