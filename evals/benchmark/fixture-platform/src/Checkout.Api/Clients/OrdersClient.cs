using System.Net.Http.Json;
using Platform.Contracts;

namespace Checkout.Api.Clients;

/// <summary>Talks to orders over HTTP; the base address comes from Services:Orders:BaseUrl.</summary>
internal sealed class OrdersClient : IOrdersClient
{
    private readonly HttpClient _http;

    public OrdersClient(HttpClient http)
    {
        _http = http;
    }

    public async Task<CustomerView?> FindCustomerAsync(long customerId, CancellationToken cancellationToken)
    {
        using var response = await _http.GetAsync($"/api/customers/{customerId}", cancellationToken);
        return response.IsSuccessStatusCode
            ? await response.Content.ReadFromJsonAsync<CustomerView>(cancellationToken)
            : null;
    }

    public async Task<OrderView?> CreateAsync(long customerId, decimal total, CancellationToken cancellationToken)
    {
        using var response = await _http.PostAsJsonAsync("/api/orders", new CreateOrderRequest(customerId, total), cancellationToken);
        return response.IsSuccessStatusCode
            ? await response.Content.ReadFromJsonAsync<OrderView>(cancellationToken)
            : null;
    }
}
