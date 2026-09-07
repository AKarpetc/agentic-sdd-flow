using FluentAssertions;
using Microsoft.Extensions.Options;
using NSubstitute;
using Platform.Contracts;
using Pricing.Api.Configuration;
using Pricing.Api.Services;

namespace Platform.Tests;

public sealed class PricingServiceTests
{
    [Fact]
    public void Quote_AppliesThePromotionOnceTheSubtotalQualifies()
    {
        var pricing = Service();

        var outcome = pricing.Quote(new QuoteRequest([new QuoteLine("SKU-1", 2)]));

        outcome.Quote.Should().NotBeNull();
        outcome.Quote!.Subtotal.Should().Be(20.00m);
        outcome.Quote.Discounts.Should().ContainSingle().Which.Code.Should().Be("PCT10");
        outcome.Quote.Total.Should().Be(18.00m);
    }

    [Fact]
    public void Quote_NamesTheSkuItCannotPrice()
    {
        var pricing = Service();

        var outcome = pricing.Quote(new QuoteRequest([new QuoteLine("SKU-9", 1)]));

        outcome.Quote.Should().BeNull();
        outcome.UnknownSku.Should().Be("SKU-9");
    }

    private static PricingService Service()
    {
        var settings = new PricingSettings
        {
            PriceList = new Dictionary<string, decimal> { ["SKU-1"] = 10.00m, ["SKU-2"] = 25.00m },
            Promotions = [new PromotionSettings { Code = "PCT10", Kind = "Percentage", Value = 10m, MinSubtotal = 20.00m }],
        };
        var options = Substitute.For<IOptionsSnapshot<PricingSettings>>();
        options.Value.Returns(settings);
        return new PricingService(options);
    }
}
