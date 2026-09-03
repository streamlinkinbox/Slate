//============================================================================================================================================
// 📦 Project-Zero/Source/GameExecution.cpp — Project-Zero Native Interactive Window and ReSTIR Photometric Viewport Entry Point
//============================================================================================================================================

#include "RendererHost.h"
#include "FlyThroughSolver.h"
#include "../../../DeviceExchange/WindowExchange.h"
#include "../../../DeviceExchange/InputExchange.h"
#include "../../../DeviceExchange/DiagnosticMetrics.h"
#include "../../../DisplayPresentation/ControlCentrePanel.h"
#include <iostream>
#include <chrono>
#include <vector>
#include <cstdlib>

int main(int ArgumentCount, char** ArgumentValues)
{
    std::cout << "================================================================================\n";
    std::cout << "                 PROJECT-ZERO — RESTIR PHOTOMETRIC TEST GROUND                  \n";
    std::cout << "================================================================================\n";
    std::cout << "[Project-Zero] Opening native OS display window and initializing ReSTIR engine...\n";

    bool TestModeOnly = false;
    for (int i = 1; i < ArgumentCount; ++i)
    {
        std::string_view Arg(ArgumentValues[i]);
        if (Arg == "--test" || Arg == "--benchmark" || Arg == "--headless")
        {
            TestModeOnly = true;
        }
    }

    constexpr uint32_t WindowWidth  = 1280;
    constexpr uint32_t WindowHeight = 720;
    constexpr uint32_t RenderWidth  = 640;
    constexpr uint32_t RenderHeight = 360;

    // 1. Create and Open Native OS Window (Win32 / X11 / GLFW)
    Frontier::WindowExchange Window;
    Frontier::WindowConfiguration WindowConfig{
        WindowWidth,
        WindowHeight,
        "Project-Zero — ReSTIR DI/GI Photometric Viewport [Frontier Engine]",
        false,
        true
    };

    if (!Window.OpenDisplayWindow(WindowConfig))
    {
        std::cerr << "[Project-Zero Error] Failed to open native OS display window!\n";
        return 1;
    }

    std::cout << "[Project-Zero] Native OS window created (" << WindowWidth << "x" << WindowHeight << " px).\n";

    // 2. Initialize Hardware Input, Camera, Top Notch, and ReSTIR Renderer
    Frontier::InputExchange Input;

    Frontier::ProjectZero::FlyThroughConfiguration CameraConfig{
        3.5f,                   // [m/s] base speed
        2.5f,                   // [x] boost when holding Shift
        0.003f,                 // [rad/px] mouse sensitivity
        0.5f,                   // [m/s] scroll increment
        12.0f                   // damping
    };
    Frontier::ProjectZero::FlyThroughSolver Camera(CameraConfig);
    Camera.AssignSpatialLocation(Frontier::Vector3{ 0.0f, -1.95f, 1.0f });
    Camera.AssignOrientationEuler(0.0f, 0.0f, 0.0f);
    Camera.AssignFieldOfView(55.0f);
    Camera.AssignAspectRatio(static_cast<float>(RenderWidth) / static_cast<float>(RenderHeight));

    Frontier::ControlCentrePanel ControlCentre;
    [[maybe_unused]] bool Initialized = ControlCentre.Initialize(WindowWidth, WindowHeight);

    Frontier::ProjectZero::RendererHost Renderer(RenderWidth, RenderHeight);
    std::vector<uint32_t> FrameBuffer(RenderWidth * RenderHeight, 0xFF000000u);

    // Initial warm-up render frame
    Renderer.RenderReSTIRFrame(Camera, 2);
    Renderer.CompositeFrame(ControlCentre, FrameBuffer);
    Window.PresentFrameBuffer(FrameBuffer.data(), RenderWidth, RenderHeight);

    // Export proof image on startup
    std::string PpmPath = "Diagnostics/ProjectZero_ReSTIR_GI.ppm";
    std::string PngPath = "Diagnostics/ProjectZero_ReSTIR_GI.png";
    (void)Renderer.ExportPpmImage(PpmPath);
    (void)std::system(("python3 Tools/PpmToPng.py " + PpmPath + " " + PngPath + " > /dev/null 2>&1").c_str());

    if (TestModeOnly)
    {
        std::cout << "[Project-Zero] Running automated test cycles...\n";
        for (int tick = 1; tick <= 5; ++tick)
        {
            Window.PollEvents(&Input);
            Camera.AdvanceLocomotion(Input, 1.0f / 60.0f);
            Renderer.RenderReSTIRFrame(Camera, 1);
            Renderer.CompositeFrame(ControlCentre, FrameBuffer);
            Window.PresentFrameBuffer(FrameBuffer.data(), RenderWidth, RenderHeight);
        }
        std::cout << "[Project-Zero] Test complete. Window closing.\n";
        Window.CloseDisplayWindow();
        return 0;
    }

    // 3. Main Interactive Real-Time OS Window Event Loop
    std::cout << "[Project-Zero] Interactive window loop running! (Right-Click+WASD to fly, Top Notch to configure, ESC to quit)\n";

    auto LastTime = std::chrono::high_resolution_clock::now();
    int FrameIndex = 0;

    while (!Window.ShouldClose())
    {
        auto CurrentTime = std::chrono::high_resolution_clock::now();
        float DeltaSeconds = std::chrono::duration<float>(CurrentTime - LastTime).count();
        LastTime = CurrentTime;
        DeltaSeconds = std::clamp(DeltaSeconds, 0.001f, 0.05f);

        // A. Poll native OS messages and hardware input
        Window.PollEvents(&Input);
        if (Input.IsKeyPressed(Frontier::VirtualKeyCategory::KeyEscape))
        {
            break;
        }

        // B. Unreal-style Fly-Through Camera Navigation
        Camera.AdvanceLocomotion(Input, DeltaSeconds);

        // C. Top Notch Control Centre Interaction
        ControlCentre.AdvanceInteraction(Input, Input.QueryCursorPositionX(), Input.QueryCursorPositionY());
        ControlCentre.AdvanceLocomotion(DeltaSeconds);

        // D. Render ReSTIR DI + GI Raytracing Frame
        Renderer.RenderReSTIRFrame(Camera, 1);

        // E. Composite Frame and Present to Native OS Window
        Renderer.CompositeFrame(ControlCentre, FrameBuffer);
        Window.PresentFrameBuffer(FrameBuffer.data(), RenderWidth, RenderHeight);

        ++FrameIndex;
        if (FrameIndex >= 60 && Window.QueryNativeWindowToken() == reinterpret_cast<void*>(0xDEADBEEFULL))
        {
            // Fallback for headless environments without native display server
            std::cout << "[Project-Zero] Completed " << FrameIndex << " frames on virtual display buffer. Session active.\n";
            break;
        }
    }

    std::cout << "[Project-Zero] Exiting interactive viewport session. Cleaning up...\n";
    Window.CloseDisplayWindow();
    return 0;
}
