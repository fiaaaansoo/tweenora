#include "rive/file.hpp"
#include "rive/runtime_header.hpp"
#include "rive_file_reader.hpp"
#include <catch.hpp>
#include <cstring>
#include <string>
#include <vector>

static const char* kAsset = "assets/data_binding_test_2.riv";

static std::vector<uint8_t> assetWithSignature(const std::string& signature)
{
    REQUIRE(signature.size() == 4);
    std::vector<uint8_t> bytes = ReadFile(kAsset);
    REQUIRE(bytes.size() > 4);
    REQUIRE(std::memcmp(bytes.data(), "RIVE", 4) == 0);
    std::memcpy(bytes.data(), signature.data(), 4);
    return bytes;
}

TEST_CASE("a file with the TWNR signature is read", "[file][signature]")
{
    REQUIRE(std::memcmp(rive::kRuntimeHeaderFingerprint, "TWNR", 4) == 0);

    rive::ImportResult result;
    auto file = rive::File::import(assetWithSignature("TWNR"),
                                   &gNoOpFactory,
                                   &result);
    REQUIRE(result == rive::ImportResult::success);
    REQUIRE(file != nullptr);
    REQUIRE(file->artboard() != nullptr);
}

TEST_CASE("a file with the RIVE signature is still read", "[file][signature]")
{
    rive::ImportResult result;
    auto file = rive::File::import(assetWithSignature("RIVE"),
                                   &gNoOpFactory,
                                   &result);
    REQUIRE(result == rive::ImportResult::success);
    REQUIRE(file != nullptr);
    REQUIRE(file->artboard() != nullptr);
}

TEST_CASE("a file with any other signature is rejected", "[file][signature]")
{
    const std::vector<std::string> signatures = {"XXXX",
                                                 "twnr",
                                                 "rive",
                                                 "TWNX",
                                                 "RIVR",
                                                 "TWVE",
                                                 "RINR",
                                                 std::string(4, '\0')};
    for (const std::string& signature : signatures)
    {
        CAPTURE(signature);
        rive::ImportResult result;
        auto file = rive::File::import(assetWithSignature(signature),
                                       &gNoOpFactory,
                                       &result);
        REQUIRE(result == rive::ImportResult::malformed);
        REQUIRE(file == nullptr);
    }
}

TEST_CASE("a buffer shorter than the signature is rejected",
          "[file][signature]")
{
    for (const char* signature : {"TWNR", "RIVE"})
    {
        for (size_t length = 0; length < 4; length++)
        {
            CAPTURE(signature, length);
            std::vector<uint8_t> bytes(signature, signature + length);
            rive::ImportResult result;
            auto file = rive::File::import(bytes, &gNoOpFactory, &result);
            REQUIRE(result == rive::ImportResult::malformed);
            REQUIRE(file == nullptr);
        }
    }
}
