namespace Pricing.Api.Configuration;

/// <summary>One promotion: how much it takes off, and the subtotal it starts applying at.</summary>
internal sealed class PromotionSettings
{
    public string Code { get; set; } = string.Empty;

    public string Kind { get; set; } = "Percentage";

    public decimal Value { get; set; }

    public decimal MinSubtotal { get; set; }
}
