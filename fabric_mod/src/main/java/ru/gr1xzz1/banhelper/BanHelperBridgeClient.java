package ru.gr1xzz1.banhelper;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;
import ru.gr1xzz1.banhelper.gui.BridgeConfigScreen;

public final class BanHelperBridgeClient implements ClientModInitializer {
    private static KeyBinding openGuiKey;
    @Override public void onInitializeClient(){BridgeConfig.load();BridgeSender.initialize();
        openGuiKey=KeyBindingHelper.registerKeyBinding(new KeyBinding("key.banhelper_bridge.open_gui",InputUtil.Type.KEYSYM,GLFW.GLFW_KEY_RIGHT_SHIFT,"category.banhelper_bridge"));
        ClientTickEvents.END_CLIENT_TICK.register(client->{while(openGuiKey.wasPressed())client.setScreen(new BridgeConfigScreen(client.currentScreen));VerificationTracker.tick(client);});
        HudRenderCallback.EVENT.register((context,tickCounter)->{if(!BridgeConfig.DATA.hudEnabled)return;MinecraftClient c=MinecraftClient.getInstance();String label=switch(ConnectionState.state()){case CONNECTED->"§a● BanHelper: Connected";case CONNECTING->"§e● BanHelper: Connecting";case AUTH_ERROR->"§c● BanHelper: Invalid token";case OFFLINE->"§c● BanHelper: Offline";};context.drawTextWithShadow(c.textRenderer,Text.literal(label),8,8,0xFFFFFF);});
        System.out.println("[BanHelper Bridge] Fabric 1.21.4 bridge v2.0.0 loaded");}
}
