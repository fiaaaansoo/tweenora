#include "rive/animation/layer_state.hpp"
#include "rive/animation/state_machine_bool.hpp"
#include "rive/animation/state_machine_input_instance.hpp"
#include "rive/animation/state_machine_instance.hpp"
#include "rive/animation/state_machine_number.hpp"
#include "rive/animation/state_machine_trigger.hpp"
#include "rive/artboard.hpp"
#include "rive/event.hpp"
#include "rive/event_report.hpp"
#include "rive/file.hpp"
#include "utils/no_op_factory.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <memory>
#include <map>
#include <string>
#include <vector>

namespace
{
struct Value
{
    bool isString = false;
    bool isBool = false;
    std::string text;
    double number = 0;
    bool flag = false;
};

using Object = std::map<std::string, Value>;

void skipSpace(const std::string& s, size_t& i)
{
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r'))
    {
        i++;
    }
}

bool parseString(const std::string& s, size_t& i, std::string& out)
{
    if (i >= s.size() || s[i] != '"')
    {
        return false;
    }
    i++;
    out.clear();
    while (i < s.size() && s[i] != '"')
    {
        if (s[i] == '\\' && i + 1 < s.size())
        {
            i++;
            switch (s[i])
            {
                case 'n':
                    out += '\n';
                    break;
                case 't':
                    out += '\t';
                    break;
                default:
                    out += s[i];
                    break;
            }
        }
        else
        {
            out += s[i];
        }
        i++;
    }
    if (i >= s.size())
    {
        return false;
    }
    i++;
    return true;
}

bool parseObject(const std::string& s, Object& out)
{
    size_t i = 0;
    skipSpace(s, i);
    if (i >= s.size() || s[i] != '{')
    {
        return false;
    }
    i++;
    for (;;)
    {
        skipSpace(s, i);
        if (i < s.size() && s[i] == '}')
        {
            return true;
        }
        std::string key;
        if (!parseString(s, i, key))
        {
            return false;
        }
        skipSpace(s, i);
        if (i >= s.size() || s[i] != ':')
        {
            return false;
        }
        i++;
        skipSpace(s, i);
        Value value;
        if (i < s.size() && s[i] == '"')
        {
            value.isString = true;
            if (!parseString(s, i, value.text))
            {
                return false;
            }
        }
        else if (s.compare(i, 4, "true") == 0)
        {
            value.isBool = true;
            value.flag = true;
            i += 4;
        }
        else if (s.compare(i, 5, "false") == 0)
        {
            value.isBool = true;
            i += 5;
        }
        else
        {
            char* end = nullptr;
            value.number = strtod(s.c_str() + i, &end);
            if (end == s.c_str() + i)
            {
                return false;
            }
            i = end - s.c_str();
        }
        out[key] = value;
        skipSpace(s, i);
        if (i < s.size() && s[i] == ',')
        {
            i++;
        }
    }
}

std::string escape(const std::string& in)
{
    std::string out;
    for (char c : in)
    {
        switch (c)
        {
            case '"':
                out += "\\\"";
                break;
            case '\\':
                out += "\\\\";
                break;
            case '\n':
                out += "\\n";
                break;
            case '\t':
                out += "\\t";
                break;
            default:
                if (static_cast<unsigned char>(c) < 0x20)
                {
                    char buffer[8];
                    snprintf(buffer, sizeof buffer, "\\u%04x", c);
                    out += buffer;
                }
                else
                {
                    out += c;
                }
        }
    }
    return "\"" + out + "\"";
}

std::string number(double value)
{
    char buffer[64];
    snprintf(buffer, sizeof buffer, "%.9g", value);
    std::string text = buffer;
    if (text.find_first_of(".eE") == std::string::npos)
    {
        text += ".0";
    }
    return text;
}

std::string str(const Object& o, const char* key)
{
    auto it = o.find(key);
    return it == o.end() ? std::string() : it->second.text;
}

double num(const Object& o, const char* key)
{
    auto it = o.find(key);
    return it == o.end() ? 0 : it->second.number;
}

bool flag(const Object& o, const char* key)
{
    auto it = o.find(key);
    return it != o.end() && it->second.flag;
}

std::string describeAction(const Object& o)
{
    std::string op = str(o, "op");
    std::string out = "{\"op\": " + escape(op);
    if (op == "advance")
    {
        out += ", \"dt\": " + number(num(o, "dt"));
    }
    else if (op == "bool")
    {
        out += ", \"name\": " + escape(str(o, "name")) + ", \"value\": " +
               (flag(o, "value") ? "true" : "false");
    }
    else if (op == "number")
    {
        out += ", \"name\": " + escape(str(o, "name")) + ", \"value\": " +
               number(num(o, "value"));
    }
    else if (op == "trigger")
    {
        out += ", \"name\": " + escape(str(o, "name"));
    }
    else if (op == "pointer")
    {
        out += ", \"kind\": " + escape(str(o, "kind")) +
               ", \"x\": " + number(num(o, "x")) +
               ", \"y\": " + number(num(o, "y"));
    }
    return out + "}";
}

std::string inputKind(uint16_t coreType)
{
    if (coreType == rive::StateMachineBool::typeKey)
    {
        return "bool";
    }
    if (coreType == rive::StateMachineNumber::typeKey)
    {
        return "number";
    }
    if (coreType == rive::StateMachineTrigger::typeKey)
    {
        return "trigger";
    }
    return "other";
}

std::string describeInputs(const rive::StateMachineInstance* machine)
{
    std::string out = "[";
    for (size_t i = 0; i < machine->inputCount(); i++)
    {
        auto* input = machine->input(i);
        if (i != 0)
        {
            out += ", ";
        }
        std::string kind = inputKind(input->inputCoreType());
        out += "{\"name\": " + escape(input->name()) +
               ", \"kind\": " + escape(kind) + ", \"value\": ";
        if (kind == "bool")
        {
            out += static_cast<const rive::SMIBool*>(input)->value() ? "true"
                                                                     : "false";
        }
        else if (kind == "number")
        {
            out += number(static_cast<const rive::SMINumber*>(input)->value());
        }
        else
        {
            out += "null";
        }
        out += "}";
    }
    return out + "]";
}

std::string describeChanged(const rive::StateMachineInstance* machine)
{
    std::string out = "[";
    size_t count = machine->stateChangedCount();
    for (size_t i = 0; i < count; i++)
    {
        auto* state = machine->stateChangedByIndex(i);
        if (i != 0)
        {
            out += ", ";
        }
        out += "{\"index\": " + std::to_string(i) + ", \"state\": " +
               std::to_string(state == nullptr ? -1 : (int)state->coreType()) +
               "}";
    }
    return out + "]";
}

std::string describeEvents(const rive::StateMachineInstance* machine)
{
    std::string out = "[";
    size_t count = machine->reportedEventCount();
    for (size_t i = 0; i < count; i++)
    {
        auto report = machine->reportedEventAt(i);
        if (i != 0)
        {
            out += ", ";
        }
        out += "{\"name\": " + escape(report.event()->name()) +
               ", \"delay\": " + number(report.secondsDelay()) + "}";
    }
    return out + "]";
}

void applyAction(rive::StateMachineInstance* machine, const Object& action)
{
    std::string op = str(action, "op");
    if (op == "advance")
    {
        machine->advanceAndApply(static_cast<float>(num(action, "dt")));
    }
    else if (op == "bool")
    {
        if (auto* input = machine->getBool(str(action, "name")))
        {
            input->value(flag(action, "value"));
        }
    }
    else if (op == "number")
    {
        if (auto* input = machine->getNumber(str(action, "name")))
        {
            input->value(static_cast<float>(num(action, "value")));
        }
    }
    else if (op == "trigger")
    {
        if (auto* input = machine->getTrigger(str(action, "name")))
        {
            input->fire();
        }
    }
    else if (op == "pointer")
    {
        rive::Vec2D position(static_cast<float>(num(action, "x")),
                             static_cast<float>(num(action, "y")));
        std::string kind = str(action, "kind");
        if (kind == "down")
        {
            machine->pointerDown(position);
        }
        else if (kind == "move")
        {
            machine->pointerMove(position);
        }
        else
        {
            machine->pointerUp(position);
        }
    }
}
} // namespace

int main(int argc, char** argv)
{
    if (argc < 3)
    {
        fprintf(stderr,
                "usage: sm_trace <file> <script.jsonl> [artboard] "
                "[state machine]\n");
        return 2;
    }
    std::string path = argv[1];
    std::string artboardName = argc > 3 ? argv[3] : "";
    std::string machineName = argc > 4 ? argv[4] : "";

    std::ifstream fileStream(path, std::ios::binary);
    if (!fileStream.good())
    {
        fprintf(stderr, "cannot read %s\n", path.c_str());
        return 2;
    }
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(fileStream)),
                               std::istreambuf_iterator<char>());

    const bool describe = std::string(argv[2]) == "--describe";
    std::ifstream scriptStream(describe ? "" : argv[2]);
    if (!describe && !scriptStream.good())
    {
        fprintf(stderr, "cannot read %s\n", argv[2]);
        return 2;
    }
    std::vector<Object> actions;
    std::string line;
    while (std::getline(scriptStream, line))
    {
        if (line.find_first_not_of(" \t\r") == std::string::npos)
        {
            continue;
        }
        Object action;
        if (!parseObject(line, action))
        {
            fprintf(stderr, "bad script line: %s\n", line.c_str());
            return 2;
        }
        actions.push_back(action);
    }

    rive::NoOpFactory factory;
    rive::ImportResult result = rive::ImportResult::success;
    auto file = rive::File::import(bytes, &factory, &result, nullptr);
    if (file == nullptr)
    {
        fprintf(stderr, "import failed\n");
        return 3;
    }
    std::unique_ptr<rive::ArtboardInstance> artboard =
        artboardName.empty() ? file->artboardDefault()
                             : file->artboardNamed(artboardName);
    if (artboard == nullptr)
    {
        fprintf(stderr, "no such artboard\n");
        return 3;
    }
    std::unique_ptr<rive::StateMachineInstance> machine;
    if (!machineName.empty())
    {
        machine = artboard->stateMachineNamed(machineName);
    }
    else
    {
        machine = artboard->defaultStateMachine();
        if (machine == nullptr)
        {
            machine = artboard->stateMachineAt(0);
        }
    }
    if (machine == nullptr)
    {
        fprintf(stderr, "no such state machine\n");
        return 3;
    }

    if (describe)
    {
        auto bounds = artboard->bounds();
        std::string inputs = "[";
        for (size_t i = 0; i < machine->inputCount(); i++)
        {
            auto* input = machine->input(i);
            if (i != 0)
            {
                inputs += ", ";
            }
            inputs += "{\"name\": " + escape(input->name()) +
                      ", \"kind\": " + escape(inputKind(input->inputCoreType())) + "}";
        }
        inputs += "]";
        printf("{\"artboard\": %s, \"stateMachine\": %s, \"width\": %s, "
               "\"height\": %s, \"inputs\": %s}\n",
               escape(artboard->name()).c_str(),
               escape(machine->name()).c_str(),
               number(bounds.width()).c_str(),
               number(bounds.height()).c_str(),
               inputs.c_str());
        return 0;
    }

    std::string name = path;
    size_t slash = name.find_last_of("/\\");
    if (slash != std::string::npos)
    {
        name = name.substr(slash + 1);
    }
    printf("{\"trace\": 1, \"file\": %s, \"artboard\": %s, \"stateMachine\": "
           "%s}\n",
           escape(name).c_str(),
           escape(artboard->name()).c_str(),
           escape(machine->name()).c_str());
    for (size_t i = 0; i < actions.size(); i++)
    {
        applyAction(machine.get(), actions[i]);
        printf("{\"step\": %zu, \"action\": %s, \"needsAdvance\": %s, "
               "\"changed\": %s, \"inputs\": %s, \"events\": %s}\n",
               i,
               describeAction(actions[i]).c_str(),
               machine->needsAdvance() ? "true" : "false",
               describeChanged(machine.get()).c_str(),
               describeInputs(machine.get()).c_str(),
               describeEvents(machine.get()).c_str());
    }
    printf("{\"end\": true, \"steps\": %zu}\n", actions.size());
    return 0;
}
