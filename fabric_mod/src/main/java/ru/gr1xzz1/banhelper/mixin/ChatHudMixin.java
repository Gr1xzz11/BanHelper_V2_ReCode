package ru.gr1xzz1.banhelper.mixin;

import net.minecraft.client.gui.hud.ChatHud;
import net.minecraft.text.Text;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import ru.gr1xzz1.banhelper.BanParser;
import ru.gr1xzz1.banhelper.BridgeConfig;
import ru.gr1xzz1.banhelper.BridgeSender;
import ru.gr1xzz1.banhelper.HoverExtractor;
import ru.gr1xzz1.banhelper.VerificationTracker;

@Mixin(ChatHud.class)
public abstract class ChatHudMixin {
    @Inject(method = "addMessage(Lnet/minecraft/text/Text;)V", at = @At("HEAD"))
    private void banhelper$inspectMessage(Text message, CallbackInfo ci) {
        String visible = message.getString();
        VerificationTracker.inspect(visible).ifPresent(ban ->
                BridgeSender.sendAsync(ban, visible, "Причина: выход с проверки", "CHECK_TRACKER")
        );
        if (!visible.toLowerCase().contains("забанил")) return;
        var hover = HoverExtractor.extract(message, BridgeConfig.DATA.extractionMode);
        if (hover.isPresent()) {
            var extracted = hover.get();
            BanParser.parse(visible, extracted.hoverText()).ifPresent(ban ->
                    BridgeSender.sendAsync(ban, visible, extracted.hoverText(), extracted.mode())
            );
        } else {
            BanParser.parseVisible(visible).ifPresent(ban ->
                    BridgeSender.sendAsync(ban, visible, visible, "VISIBLE")
            );
        }
    }
}
