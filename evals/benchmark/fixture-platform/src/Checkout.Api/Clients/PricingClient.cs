using System.Net.Http.Json;
using Platform.Contracts;

namespace Checkout.Api.Clients;

/// <summary>Talks to pricing over HTTP; the base address comes from Services:Pricing:BaseUrl.</summary>
internal sealed class PricingClient : IPricingClient
{
    private readonly HttpClient _http;

    public PricingClient(HttpClient http)
    {
        _http = http;
    }

    public async Task<QuoteResult?> QuoteAsync(IReadOnlyList<QuoteLine> lines, CancellationToken cancellationToken)
    {
        using var response = await _http.PostAsJsonAsync("/api/pricing/quote", new QuoteRequest(lines), cancellationToken);
        return response.IsSuccessStatusCode
            ? await response.Content.ReadFromJsonAsync<QuoteResult>(cancellationToken)
            : null;
    }
}
