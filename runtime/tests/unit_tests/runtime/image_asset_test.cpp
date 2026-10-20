#include <rive/file.hpp>
#include <rive/node.hpp>
#include <rive/shapes/clipping_shape.hpp>
#include <rive/shapes/rectangle.hpp>
#include <rive/shapes/image.hpp>
#include <rive/assets/image_asset.hpp>
#include <utils/no_op_renderer.hpp>
#include "rive_file_reader.hpp"
#include <catch.hpp>
#include <cstdio>

TEST_CASE("image assets loads correctly", "[assets]")
{
    auto file = ReadRiveFile("assets/in_band_asset.riv");

    auto node = file->artboard()->find("1x1.png");
    REQUIRE(node != nullptr);
    REQUIRE(node->is<rive::Image>());
    auto image = node->as<rive::Image>();
    REQUIRE(image->imageAsset() != nullptr);
    REQUIRE(image->imageAsset()->decodedByteSize == 308);

    file->artboard()->updateComponents();

    rive::NoOpRenderer renderer;
    file->artboard()->draw(&renderer);
}
